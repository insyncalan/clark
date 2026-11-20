"""Row 1327: the four approved Update rows. Released | <date> · <size>; Last checked | <time> or Not checked yet; Use a file instead;
Updated to clark <X>. Classic, 1400 then 900. The words are logic/update.js ROWS; the size words are built by updates.size_text.

Run: python3 dev/run_tests.py test_update_rows_1327
"""
import unittest

from test_update_page import OK, STATUS, InBrowser, lit

BASE = {**STATUS, "available": None, "line": None, "last": None}
AVAIL = {"state": "avail", "version": "0.3.2", "notes": "Faster.", "checked": "19-11-2026 11:42", "date": "18-11-2026", "size": "38 MB"}
LABELS = "[...document.querySelectorAll('#update .upd-l')].map(e => e.textContent)"


class Words(InBrowser):
    def test_released_joins_date_and_size_and_leaves_out_what_is_not_known(self):
        for date, size, want in (("18-11-2026", "4.2 MB", "18-11-2026 · 4.2 MB"), ("18-11-2026", "", "18-11-2026"), ("", "12 MB", "12 MB"), ("", "", "")):
            got = self.val(f"T.logic.releasedText(T.logic.fetchView({{latest: {{state: 'avail', version: '1', date: {lit(date)}, size: {lit(size)}}}}}))")
            self.assertEqual(want, got, (date, size))
        self.assertEqual("", self.val("T.logic.releasedText({kind: 'latest'})"))

    def test_last_checked_is_today_then_the_stamp_then_not_checked_yet(self):
        for when, want in (("20-11-2026 11:42", "Today 11:42"), ("18-11-2026 11:42", "18-11-2026 11:42"), ("", "Not checked yet"),
                           (None, "Not checked yet"), ("yesterday", "Not checked yet")):
            self.assertEqual(want, self.val(f"T.logic.checkedText({lit(when)}, '20-11-2026')"), when)

    def test_the_day_is_spelled_as_the_stamp_is(self):
        self.assertEqual("05-01-2026", self.val("T.logic.dayText(new Date(2026, 0, 5))"))
        self.assertEqual("20-11-2026", self.val("T.logic.dayText(new Date(2026, 10, 20))"))

    def test_the_approved_titles(self):
        self.assertEqual(["Released", "Last checked", "Not checked yet", "Use a file instead", "Updated to clark 1.3.2"],
                         [self.val("T.logic.ROWS.released"), self.val("T.logic.ROWS.checked"), self.val("T.logic.ROWS.notChecked"),
                          self.val("T.logic.ROWS.file"), self.val("T.logic.updatedTo('1.3.2')")])
        self.assertEqual("0.3.1", self.val("T.logic.statusView({last: {to: '0.3.1', line: 'Last update: a → b on c.'}}).lastTo"))
        self.assertEqual("", self.val("T.logic.statusView({}).lastTo"))


class OnThePage(InBrowser):
    def each(self, status):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.load(width=width)
                self.replies(status=OK(status))
                self.mount()
                yield width

    def test_a_newer_release_shows_released_and_last_checked_rows_in_order(self):
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "idle"}}):
            self.assertEqual(["Installed", "Update", "Released", "Last checked", "Use a file instead"], self.val(LABELS))
            self.assertEqual("18-11-2026 · 38 MB", self.text("#update-released"))
            self.assertEqual("19-11-2026 11:42", self.text("#update-checked"))
            self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))

    def test_before_the_first_look_the_row_says_not_checked_yet_and_there_is_no_released_row(self):
        for _ in self.each({**BASE, "latest": {"state": "looking"}, "fetch": {"state": "idle"}}):
            self.assertEqual(["Installed", "Update", "Last checked", "Use a file instead"], self.val(LABELS))
            self.assertEqual("Not checked yet", self.text("#update-checked"))
            self.assertFalse(self.present("#update-released"))

    def test_a_release_with_no_size_shows_the_date_alone(self):
        for _ in self.each({**BASE, "latest": {**AVAIL, "size": ""}, "fetch": {"state": "idle"}}):
            self.assertEqual("18-11-2026", self.text("#update-released"))

    def test_a_server_that_does_not_look_online_shows_neither_new_row(self):
        for _ in self.each({**BASE}):
            self.assertEqual(["Installed", "Update", "Use a file instead"], self.val(LABELS))

    def test_the_last_update_row_is_titled_with_the_version_it_went_to(self):
        last = {"from": "0.3.0", "to": "0.3.1", "line": "Last update: 0.3.0 → 0.3.1 on 01-11-2026."}
        for _ in self.each({**BASE, "last": last}):
            self.assertEqual("Updated to clark 0.3.1", self.text("#update-last-l"))
            self.assertEqual("0.3.0 → 0.3.1 on 01-11-2026.", self.text("#update-last p"))
        for _ in self.each({**BASE, "last": {"line": "Last update: x."}}):
            self.assertEqual("Last update", self.text("#update-last-l"))


if __name__ == "__main__":
    unittest.main()
