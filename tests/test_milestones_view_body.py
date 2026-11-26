"""Row 1230: the Milestones section's view setting {n, scroll, tracker} kept in the milestones section's body, the same three keys and the
same checker as the use case summary (section_bodies.py, publish.py: guarded). An empty body means the defaults and the section stays in the
published file.

Run: python3 dev/run_tests.py test_milestones_view_body
"""
import json
import unittest

from clark import changes, publish, section_bodies as sb, store as store_module
from test_changes import KIND
import test_delete_any_section as _test_delete_any_section
import test_publish_section_bodies as _test_publish_section_bodies

RULES = sb.Rules(plain=lambda t: True, visible=lambda t: True)


def check(value):
    return sb.check("milestones", value if isinstance(value, str) else json.dumps(value), RULES)


class PublishedPick(unittest.TestCase):
    def test_published_picks_the_three_keys_by_name_and_nothing_else(self):
        self.assertEqual(sb.published("milestones", {"n": 3, "scroll": True, "evil": 1}), {"n": 3, "scroll": True})
        self.assertEqual(sb.published("milestones", {"tracker": "bottom", "x": "y"}), {"tracker": "bottom"})
        self.assertEqual(sb.published("milestones", "text"), {})


class Checker(unittest.TestCase):
    def test_the_type_is_registered_everywhere(self):
        self.assertIn("milestones", sb.BODY_TYPES)
        self.assertIn("milestones", store_module.BODY_TYPES)
        self.assertIn("milestones", sb.CHECKERS)
        self.assertEqual(sb.EMPTY["milestones"], "")

    def test_good_bodies_are_stored_with_only_the_keys_given(self):
        # Row 1234 (c): this used to pin "all three keys always"; a tracker-only click would then write n and flip the section to "count chosen",
        # so each key now stays out of the text until it is written.
        self.assertEqual(json.loads(check({})), {})
        self.assertEqual(json.loads(check({"n": 3})), {"n": 3})
        self.assertEqual(json.loads(check({"scroll": True})), {"scroll": True})
        self.assertEqual(json.loads(check({"tracker": "off"})), {"tracker": "off"})
        self.assertNotIn("n", json.loads(check({"tracker": "bottom"})))
        self.assertEqual(json.loads(check({"n": "all", "scroll": True, "tracker": "bottom"})), {"n": "all", "scroll": True, "tracker": "bottom"})
        for n in (1, 1000):
            self.assertEqual(json.loads(check({"n": n}))["n"], n)

    def test_saving_a_stored_body_again_changes_nothing(self):
        once = check({"n": 2, "tracker": "bottom"})
        self.assertEqual(check(once), once)

    def test_an_empty_body_is_stored_empty(self):
        self.assertEqual(sb.check("milestones", "", RULES), "")
        self.assertEqual(sb.check("milestones", None, RULES), "")

    def test_bad_bodies_are_refused_without_quoting_them(self):
        bad = ['[]', '[1]', '"x"', '{"x": 1}', '{"n": 0}', '{"n": -1}', '{"n": 1001}', '{"n": true}', '{"n": null}', '{"n": "7"}',
               '{"n": "All"}', '{"n": "x"}', '{"n": 2.5}', '{"scroll": 1}', '{"scroll": "true"}', '{"scroll": null}',
               '{"tracker": "left"}', '{"tracker": "x"}', '{"tracker": ""}', '{"tracker": "TOP"}', '{"tracker": null}', '{"n": 1, "n": 2}', '{"v": 1}',
               '{"n": NaN}', '{"tracker": "ZQMARK\\u0007"}', "not json"]
        for text in bad:
            with self.subTest(body=text):
                with self.assertRaises(sb.Bad) as e:
                    check(text)
                self.assertNotIn("ZQMARK", str(e.exception))

    def test_published_carries_the_three_keys_flat(self):
        self.assertEqual(sb.published("milestones", {"n": 3, "scroll": True, "tracker": "off"}), {"n": 3, "scroll": True, "tracker": "off"})
        self.assertEqual(sb.published("milestones", {"n": "all", "scroll": False, "tracker": "top"})["n"], "all")

    def test_published_carries_only_the_keys_the_body_holds(self):
        self.assertEqual(sb.published("milestones", {"tracker": "off"}), {"tracker": "off"})
        self.assertEqual(sb.published("milestones", {"scroll": True}), {"scroll": True})
        self.assertEqual(sb.published("milestones", {}), {})


class Route(_test_delete_any_section.Base):
    def ms(self):
        return self.of_type("milestones")[0]["id"]

    def write(self, ref, body):
        return self.change(self.req("update", id=ref, changes={"body": body}))

    def stored(self, ref):
        return self.s.read(KIND, ref=ref)["body"]

    def test_a_view_is_written_in_one_step_and_one_undo_puts_it_back(self):
        ref = self.ms()
        self.assertEqual(self.stored(ref), "")
        status, got = self.write(ref, json.dumps({"n": 3, "scroll": True, "tracker": "off"}))
        self.assertEqual((status, got.get("message")), (200, None), got)
        self.assertEqual(json.loads(self.stored(ref)), {"n": 3, "scroll": True, "tracker": "off"})
        status, got = self.write(ref, json.dumps({"n": 8}))
        self.assertEqual(status, 200, got)
        self.assertEqual(json.loads(self.stored(ref)), {"n": 8})
        undone = self.undone(got["apply_id"])
        self.assertEqual(undone[0], 200, undone)
        self.assertEqual(json.loads(self.stored(ref)), {"n": 3, "scroll": True, "tracker": "off"})

    def test_a_bad_view_is_refused_and_nothing_is_written(self):
        ref = self.ms()
        before = self.snapshot()
        status, got = self.write(ref, json.dumps({"n": 0}))
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stored(ref), "")

    def test_a_tracker_only_write_stores_the_tracker_alone(self):
        ref = self.ms()
        status, got = self.write(ref, json.dumps({"tracker": "bottom"}))
        self.assertEqual(status, 200, got)
        self.assertEqual(json.loads(self.stored(ref)), {"tracker": "bottom"})


class InFile(_test_publish_section_bodies.Published, _test_delete_any_section.Base):
    def ms(self):
        return self.of_type("milestones")[0]["id"]

    def test_an_empty_body_keeps_the_section_in_the_file_with_no_setting(self):
        ref = self.ms()
        got = self.sections()
        self.assertIn(ref, got)
        self.assertEqual(set(got[ref]), {"id", "type", "title", "beside"})

    def test_a_saved_view_reaches_the_entry_and_cannot_override_its_own_keys(self):
        ref = self.ms()
        self.write(ref, json.dumps({"n": 3, "scroll": True, "tracker": "bottom"}))
        got = self.sections()[ref]
        self.assertEqual((got["n"], got["scroll"], got["tracker"]), (3, True, "bottom"))
        self.assertEqual((got["id"], got["type"]), (ref, "milestones"))

    def test_a_tracker_only_view_reaches_the_entry_with_the_tracker_alone(self):
        ref = self.ms()
        self.write(ref, json.dumps({"tracker": "bottom"}))
        got = self.sections()[ref]
        self.assertEqual((got["tracker"], "n" in got, "scroll" in got), ("bottom", False, False))

    def test_a_bad_stored_body_still_keeps_the_section(self):
        ref = self.ms()
        for bad in ("not json", '{"n": 0}', "[]"):
            with self.subTest(body=bad):
                self.raw(ref, bad)
                self.assertIn(ref, self.sections())

    def test_the_file_keeps_every_milestone_whatever_the_count_and_scroll_are(self):
        # The page slices to the count; the published file never does. 5 more client-visible milestones make 6 in all.
        with self.s.step("dashboard", "Demo User") as st:
            for i in range(5):
                st.create("milestones", {"project": "ABC", "name": f"Extra {i}", "baseline_date": f"2030-0{4 + i}-01", "source": "demo"})
        ref = self.ms()
        for scroll in (False, True):
            with self.subTest(scroll=scroll):
                self.write(ref, json.dumps({"n": 2, "scroll": scroll, "tracker": "bottom"}))
                built = self.build()["published"]
                self.assertEqual(len(built["data"]["milestones"]), 6)
                entry = {s["id"]: s for s in built["sections"]}[ref]
                self.assertEqual((entry["n"], entry["scroll"], entry["tracker"]), (2, scroll, "bottom"))

    def test_a_hidden_section_stays_out(self):
        ref = self.ms()
        self.ok("update", id=ref, changes={"hidden": 1})
        self.assertNotIn(ref, self.sections())


if __name__ == "__main__":
    unittest.main()
