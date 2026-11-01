"""#115: the owner-name resolver and the import cap in the store (read only, guarded: store.py).

Run: python3 dev/run_tests.py test_people_resolve
The people table is filled here by fixture rows (the writers come in a later commit); the resolver and the import plan must read it
and write nothing. Fictional data only.
"""
import unittest

from _demo import DemoStore
from clark import people


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.s = self.demo.store
        self.addCleanup(self.demo.close)

    def person(self, pid, name, email=None, aliases=None, archived=0, label=None):
        self.s.con.execute("INSERT INTO people (id, name, email, aliases, archived, label, source) VALUES (?, ?, ?, ?, ?, ?, 'test')",
                           (pid, name, email, aliases, archived, label))

    def dump(self):
        return list(self.s.con.iterdump())


class Reading(Base):
    def test_an_empty_list_reads_as_empty(self):
        self.assertEqual(self.s.people(), [])
        self.assertEqual(self.s.people(archived=None), [])

    def test_live_archived_and_both(self):
        self.person("P-001", "Sam Reed")
        self.person("P-002", "Jo Park", archived=1)
        self.assertEqual([p["id"] for p in self.s.people()], ["P-001"])
        self.assertEqual([p["id"] for p in self.s.people(archived=True)], ["P-002"])
        self.assertEqual([p["id"] for p in self.s.people(archived=None)], ["P-001", "P-002"])

    def test_a_bad_filter_is_refused(self):
        with self.assertRaises(Exception):
            self.s.people(archived="yes")


class Resolver(Base):
    def setUp(self):
        super().setUp()
        self.person("P-001", "Sam Reed", "sam@x.example", aliases="Sammy;S Reed")
        self.person("P-002", "Sam Reid", label="Quay team")
        self.person("P-003", "Li Wen", archived=1)

    def test_exact_name_and_alias_match_one_person(self):
        self.assertEqual(self.s.resolve_owner("sam reed")["id"], "P-001")
        self.assertEqual(self.s.resolve_owner("  Sammy ")["id"], "P-001")

    def test_accents_and_look_alike_letters_count_as_the_same(self):
        self.person("P-004", "Zoë Hart")
        self.assertEqual(self.s.resolve_owner("Zoe Hart")["id"], "P-004")

    def test_two_people_with_a_shared_alias_match_many_and_link_no_one(self):
        self.person("P-005", "Jo Park", aliases="Sammy")
        got = self.s.resolve_owner("Sammy")
        self.assertEqual((got["status"], got["id"], got["ids"]), ("many", None, ["P-001", "P-005"]))

    def test_blank_and_tbc_are_no_person_and_raise_no_prompt(self):
        for text in ("", "  ", "TBC", "tbc", None):
            self.assertEqual(self.s.resolve_owner(text)["status"], "blank", text)

    def test_an_archived_person_is_not_matched_but_is_named(self):
        got = self.s.resolve_owner("Li Wen")
        self.assertEqual((got["status"], got["id"], got["ids"]), ("archived", None, ["P-003"]))

    def test_a_near_miss_is_never_guessed(self):
        self.assertEqual(self.s.resolve_owner("Sam Rede")["status"], "none")

    def test_resolving_writes_nothing_and_makes_no_person(self):
        before = self.dump()
        for text in ("Sam Reed", "Nobody Here", "TBC", "Li Wen"):
            self.s.resolve_owner(text)
        self.assertEqual(self.dump(), before)
        self.assertEqual(len(self.s.people(archived=None)), 3)


class ImportCap(Base):
    def test_more_than_the_row_limit_is_refused_whole(self):
        text = "\n".join(f"P{i}\tp{i}@x.example" for i in range(people.ROW_LIMIT + 1))
        plan = self.s.plan_people_import(text)
        self.assertEqual((plan["rows"], plan["ok"]), ([], False))
        self.assertTrue(plan["problems"][0].startswith("That is more than"))

    def test_the_row_limit_itself_is_taken(self):
        text = "\n".join(f"P{i}\tp{i}@x.example" for i in range(people.ROW_LIMIT))
        plan = self.s.plan_people_import(text)
        self.assertEqual((len(plan["rows"]), plan["ok"]), (people.ROW_LIMIT, True))

    def test_too_much_text_is_refused_before_it_is_read_as_rows(self):
        text = "Sam Reed\t" + "x" * (people.TEXT_LIMIT + 1)
        plan = self.s.plan_people_import(text)
        self.assertEqual((plan["rows"], plan["ok"]), ([], False))
        self.assertTrue(plan["problems"][0].startswith("That is too much text"))

    def test_an_email_already_on_the_list_is_named_and_a_known_name_is_marked_same(self):
        self.person("P-001", "Sam Reed", "sam@x.example")
        plan = self.s.plan_people_import("Sam Reed\tsam@x.example\nJo Park\tjo@x.example\nSam Reed\tother@x.example\n")
        self.assertFalse(plan["ok"])
        self.assertIn("Row 1:", plan["problems"][0])
        self.assertIn("Sam Reed", plan["problems"][0])
        self.assertEqual([r["same"] for r in plan["rows"]], [["P-001"], [], ["P-001"]])

    def test_planning_writes_nothing(self):
        self.person("P-001", "Sam Reed", "sam@x.example")
        before = self.dump()
        self.s.plan_people_import("Jo Park\tjo@x.example\nSam Reed\tsam@x.example\n")
        self.assertEqual(self.dump(), before)

    def test_a_clean_paste_is_ok(self):
        plan = self.s.plan_people_import("name\temail\nJo Park\tjo@x.example\n")
        self.assertTrue(plan["ok"])
        self.assertEqual(plan["rows"][0]["clean"]["email"], "jo@x.example")


if __name__ == "__main__":
    unittest.main()
