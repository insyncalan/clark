"""Row 1234: the use case summary's view setting {n, scroll, tracker} kept in the usecases section's body (section_bodies.py,
store.py, publish.py: guarded). An empty body means the defaults and the section stays in the published file.

Run: python3 dev/run_tests.py test_usecases_view_body
"""
import json
import unittest

from clark import changes, publish, section_bodies as sb, store as store_module
from test_changes import KIND
import test_delete_any_section as _test_delete_any_section
import test_publish_section_bodies as _test_publish_section_bodies

RULES = sb.Rules(plain=lambda t: True, visible=lambda t: True)


def check(value):
    return sb.check("usecases", value if isinstance(value, str) else json.dumps(value), RULES)


class PublishedPick(unittest.TestCase):
    def test_published_picks_the_three_keys_by_name_and_nothing_else(self):
        self.assertEqual(sb.published("usecases", {"n": 3, "scroll": True, "evil": 1}), {"n": 3, "scroll": True})
        self.assertEqual(sb.published("usecases", {"tracker": "bottom", "x": "y"}), {"tracker": "bottom"})
        self.assertEqual(sb.published("usecases", "text"), {})


class Checker(unittest.TestCase):
    def test_the_type_is_registered_everywhere(self):
        self.assertIn("usecases", sb.BODY_TYPES)
        self.assertIn("usecases", store_module.BODY_TYPES)
        self.assertIn("usecases", sb.CHECKERS)
        self.assertEqual(sb.EMPTY["usecases"], "")

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
        self.assertEqual(sb.check("usecases", "", RULES), "")
        self.assertEqual(sb.check("usecases", None, RULES), "")

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
        self.assertEqual(sb.published("usecases", {"n": 3, "scroll": True, "tracker": "off"}), {"n": 3, "scroll": True, "tracker": "off"})
        self.assertEqual(sb.published("usecases", {"n": "all", "scroll": False, "tracker": "top"})["n"], "all")

    def test_published_carries_only_the_keys_the_body_holds(self):
        self.assertEqual(sb.published("usecases", {"tracker": "off"}), {"tracker": "off"})
        self.assertEqual(sb.published("usecases", {"scroll": True}), {"scroll": True})
        self.assertEqual(sb.published("usecases", {}), {})


class Route(_test_delete_any_section.Base):
    def uc(self):
        return self.of_type("usecases")[0]["id"]

    def write(self, ref, body):
        return self.change(self.req("update", id=ref, changes={"body": body}))

    def stored(self, ref):
        return self.s.read(KIND, ref=ref)["body"]

    def test_a_view_is_written_in_one_step_and_one_undo_puts_it_back(self):
        ref = self.uc()
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
        ref = self.uc()
        before = self.snapshot()
        status, got = self.write(ref, json.dumps({"n": 0}))
        self.assertEqual((status, got["ok"]), (400, False))
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(self.stored(ref), "")

    def test_a_tracker_only_write_stores_the_tracker_alone(self):
        ref = self.uc()
        status, got = self.write(ref, json.dumps({"tracker": "bottom"}))
        self.assertEqual(status, 200, got)
        self.assertEqual(json.loads(self.stored(ref)), {"tracker": "bottom"})


class InFile(_test_publish_section_bodies.Published, _test_delete_any_section.Base):
    def uc(self):
        return self.of_type("usecases")[0]["id"]

    def test_an_empty_body_keeps_the_section_in_the_file_with_no_setting(self):
        ref = self.uc()
        got = self.sections()
        self.assertIn(ref, got)
        self.assertEqual(set(got[ref]), {"id", "type", "title", "beside"})

    def test_a_saved_view_reaches_the_entry_and_cannot_override_its_own_keys(self):
        ref = self.uc()
        self.write(ref, json.dumps({"n": 3, "scroll": True, "tracker": "bottom"}))
        got = self.sections()[ref]
        self.assertEqual((got["n"], got["scroll"], got["tracker"]), (3, True, "bottom"))
        self.assertEqual((got["id"], got["type"]), (ref, "usecases"))

    def test_a_tracker_only_view_reaches_the_entry_with_the_tracker_alone(self):
        ref = self.uc()
        self.write(ref, json.dumps({"tracker": "bottom"}))
        got = self.sections()[ref]
        self.assertEqual((got["tracker"], "n" in got, "scroll" in got), ("bottom", False, False))

    def test_a_bad_stored_body_still_keeps_the_section(self):
        ref = self.uc()
        for bad in ("not json", '{"n": 0}', "[]"):
            with self.subTest(body=bad):
                self.raw(ref, bad)
                self.assertIn(ref, self.sections())

    def test_a_hidden_section_stays_out(self):
        ref = self.uc()
        self.ok("update", id=ref, changes={"hidden": 1})
        self.assertNotIn(ref, self.sections())


if __name__ == "__main__":
    unittest.main()
