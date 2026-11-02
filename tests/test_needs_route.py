"""'Needs from you' over the REAL change route with the REAL store (#405; src/clark/server.py CHANGE_BODY_LIMIT, guarded): the
fullest list the checker accepts, in every kind of letter, is not stopped by the route's size limit, and what the checker refuses
gets the checker's own words, not the route's general ones.

Run: python3 dev/run_tests.py test_needs_route
"""
import json
import unittest

from _demo import USER, DemoStore
from clark import changes, section_bodies as sb, server as sv
from clark.store import BODY_RULES
from test_tracker_route import KIND, LETTERS, Running, request

TAKEN = LETTERS[:-1]            # the four-byte letter is over the checker's own limit in this list: its own test below
OLD_LIMIT = 2 * 64 * 1024 + 4 * 1024


def rows(letter, count=sb.NEEDS_MAX_ROWS):
    return {"v": 1, "rows": [{"what": letter * sb.NEEDS_WHAT_MAX, "kind": "decision", "from": letter * sb.NEEDS_FROM_MAX,
                              "by": "2030-01-01", "hidden": 1} for _ in range(count)]}


def check(body):
    return sb.check("needs", body if isinstance(body, str) else json.dumps(body), BODY_RULES)


class Route(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.running = Running(change=changes.make_change(self.store.path, [], USER), undo=changes.make_undo(self.store.path, [], USER))
        self.addCleanup(self.running.close)
        status, _, data = self.running.api("POST", "/api/change", json.dumps(
            {"project": "ABC", "kind": KIND, "op": "new", "values": {"type": "needs", "title": "Needs from you"}}).encode())
        self.assertEqual(status, 200, data)
        self.ref = json.loads(data)["ref"]

    def post(self, body):
        status, _, data = self.running.api("POST", "/api/change", body)
        return status, json.loads(data)

    def stored(self):
        return self.store.read(KIND, ref=self.ref)["body"]

    def test_the_fullest_list_is_saved_in_every_letter_the_checker_takes_and_the_route_does_not_stop_it(self):
        for letter in TAKEN:
            for ascii_only in (True, False):
                with self.subTest(letter=repr(letter), ascii_only=ascii_only):
                    body = request(self.ref, rows(letter), ascii_only)
                    self.assertLessEqual(len(body), sv.CHANGE_BODY_LIMIT)
                    status, got = self.post(body)
                    self.assertEqual((status, got["ok"]), (200, True), got)
                    self.assertEqual(self.stored(), check(rows(letter)))

    def test_a_list_of_quote_marks_at_the_most_rows_is_more_than_the_old_132_kb_and_is_let_in(self):
        body = request(self.ref, rows('"'))
        self.assertGreater(len(body), OLD_LIMIT, "this is the case the old limit refused")
        status, got = self.post(body)
        self.assertEqual((status, got["ok"]), (200, True), got)
        self.assertEqual(self.stored(), check(rows('"')))

    def test_the_widest_list_the_checker_takes_fits_the_limit_with_room_to_spare(self):
        widest = max(len(request(self.ref, rows(letter), ascii_only)) for letter in TAKEN for ascii_only in (True, False))
        self.assertLessEqual(widest + sv.REQUEST_ENVELOPE, sv.CHANGE_BODY_LIMIT)
        self.assertGreater(widest, OLD_LIMIT)

    def test_what_the_checker_refuses_gets_its_own_words_not_the_routes(self):
        before = self.store.read(KIND, ref=self.ref)
        long_row = rows('"', 1)
        long_row["rows"][0]["what"] = '"' * (sb.NEEDS_WHAT_MAX + 1)
        for body, words in ((rows('"', sb.NEEDS_MAX_ROWS + 1), sb.NEEDS_TOO_MANY), (long_row, sb.NEEDS_WHAT_LONG), (rows(LETTERS[-1]), sv.MESSAGES["change_too_large"])):    # the checker's too-long word is shown as the change's own
            with self.subTest(words=words):
                status, got = self.post(request(self.ref, body))
                self.assertEqual((status, got["ok"], got["message"]), (400, False, words))
        self.assertEqual(self.store.read(KIND, ref=self.ref), before)

    def test_one_byte_over_the_route_limit_still_gets_the_general_words(self):
        head = b'{"project":"ABC","kind":"report_sections","op":"update","id":"' + self.ref.encode() + b'","changes":{"title":"'
        for size, over in ((sv.CHANGE_BODY_LIMIT, False), (sv.CHANGE_BODY_LIMIT + 1, True)):
            raw = head + b"x" * (size - len(head) - 3) + b'"}}'
            self.assertEqual(len(raw), size)
            status, got = self.post(raw)
            self.assertEqual(got.get("code") == "too_large", over, size)


if __name__ == "__main__":
    unittest.main()
