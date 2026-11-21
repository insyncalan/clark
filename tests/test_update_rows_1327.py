"""Row 1327: the approved Update words, rows 1 to 8 of the table (Row 1327; mock-up upgrade.html:62-74).
Classic, 1400 then 900. The words are logic/update.js; the two server sentences are updater.py FETCH_OFFLINE and FETCH_TOOBIG.

Run: python3 dev/run_tests.py test_update_rows_1327
"""
import unittest

from test_update_page import OK, STATUS, InBrowser, lit

from clark import updater as up

BASE = {**STATUS, "available": None, "line": None, "last": None}
AVAIL = {"state": "avail", "version": "0.3.2", "notes": "Faster.", "checked": "19-11-2026 11:42", "date": "18-11-2026", "size": "38 MB"}
LABELS = "[...document.querySelectorAll('#update .upd-l')].map(e => e.textContent)"
QUIET = "clark looks quietly when it starts and when you choose Check now. It never installs by itself."
OFFLINE = "clark could not reach the releases page. Check your connection, or use a file you downloaded."
FAILED = "It was not installed and nothing changed. Try the download again; if it happens again, use a file from the releases page."


class Words(InBrowser):
    def test_row_1_released_line_joins_date_and_size_and_leaves_out_what_is_not_known(self):
        for date, size, want in (("18-11-2026", "4.2 MB", "Released 18-11-2026 · 4.2 MB."), ("18-11-2026", "", "Released 18-11-2026."),
                                 ("", "12 MB", ""), ("", "", "")):
            got = self.val(f"T.logic.releasedText(T.logic.fetchView({{latest: {{state: 'avail', version: '1', date: {lit(date)}, size: {lit(size)}}}}}))")
            self.assertEqual(want, got, (date, size))
        self.assertEqual("", self.val("T.logic.releasedText({kind: 'latest'})"))
        self.assertEqual("Your projects, settings and published reports are kept.", self.val("T.logic.KEPT"))

    def test_row_2_last_checked_text_is_today_then_the_stamp_then_not_checked_yet(self):
        for when, want in (("20-11-2026 11:42", "Today 11:42. " + QUIET), ("18-11-2026 11:42", "18-11-2026 11:42. " + QUIET),
                           ("", "Not checked yet."), (None, "Not checked yet."), ("yesterday", "Not checked yet.")):
            self.assertEqual(want, self.val(f"T.logic.checkedText({lit(when)}, '20-11-2026')"), when)

    def test_row_5_the_latest_sentence_says_today_in_lower_case_and_nothing_else_carries_the_time(self):
        for when, want in (("20-11-2026 11:42", "You have the latest version (1.3.1). Last checked today 11:42."),
                           ("18-11-2026 11:42", "You have the latest version (1.3.1). Last checked 18-11-2026 11:42."),
                           ("", "You have the latest version (1.3.1)."), ("x", "You have the latest version (1.3.1).")):
            self.assertEqual(want, self.val(f"T.logic.FETCH.latest('1.3.1', {lit(when)}, '20-11-2026')"), when)

    def test_the_day_is_spelled_as_the_stamp_is(self):
        self.assertEqual("05-01-2026", self.val("T.logic.dayText(new Date(2026, 0, 5))"))
        self.assertEqual("20-11-2026", self.val("T.logic.dayText(new Date(2026, 10, 20))"))

    def test_the_approved_titles_and_sentences(self):
        self.assertEqual(["Last checked", "Not checked yet", "Use a file instead", "Updated to clark 1.3.2", "The download failed its check", "Review",
                          "For a computer with no internet. Review a clark download you already have.",
                          "clark restarted and kept everything. If something looks wrong you can go back to 1.3.1.", FAILED],
                         [self.val("T.logic.ROWS.checked"), self.val("T.logic.ROWS.notChecked"), self.val("T.logic.ROWS.file"),
                          self.val("T.logic.updatedTo('1.3.2')"), self.val("T.logic.FAILED_TITLE"), self.val("T.logic.REVIEW_LABEL"),
                          self.val("T.logic.FILE_TEXT"), self.val("T.logic.installedText('1.3.1')"), self.val("T.logic.FAILED_TEXT")])
        self.assertEqual("0.3.1", self.val("T.logic.statusView({last: {to: '0.3.1', from: '0.3.0', line: 'Last update: a → b on c.'}}).lastTo"))
        self.assertEqual("0.3.0", self.val("T.logic.statusView({last: {to: '0.3.1', from: '0.3.0', line: 'x'}}).lastFrom"))
        self.assertEqual(["", ""], self.val("[T.logic.statusView({}).lastTo, T.logic.statusView({}).lastFrom]"))

    def test_rows_7_and_8_the_server_sends_the_table_sentences(self):
        self.assertEqual(OFFLINE, up.FETCH_OFFLINE)
        self.assertEqual(FAILED, up.FETCH_TOOBIG)
        self.assertEqual(FAILED, up.FETCH_MISMATCH)


class OnThePage(InBrowser):
    def each(self, status):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.load(width=width)
                self.replies(status=OK(status))
                self.mount()
                yield width

    def today(self):
        return self.val("T.logic.dayText(new Date())")

    def test_row_1_the_ready_card_has_a_released_line_the_notes_and_what_is_kept(self):
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "idle"}}):
            self.assertEqual("Released 18-11-2026 · 38 MB.", self.text("#update-released"))
            self.assertEqual("Your projects, settings and published reports are kept.", self.text("#update-kept"))
            self.assertIn("Faster.", self.text("#update-notes"))
            self.assertEqual(["Installed", "Update", "Last checked", "Use a file instead"], self.val(LABELS))
            self.assertTrue(self.val("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
        for _ in self.each({**BASE, "latest": {**AVAIL, "size": ""}, "fetch": {"state": "idle"}}):
            self.assertEqual("Released 18-11-2026.", self.text("#update-released"))
        for _ in self.each({**BASE, "latest": {**AVAIL, "date": ""}, "fetch": {"state": "idle"}}):
            self.assertFalse(self.present("#update-released"))

    def test_row_2_last_checked_row_holds_the_sentence_and_the_check_now_button(self):
        for _ in self.each({**BASE, "latest": {**AVAIL, "checked": f"{self.today()} 11:42"}, "fetch": {"state": "idle"}}):
            self.assertEqual("Today 11:42. " + QUIET, self.text("#update-checked p"))
            self.assertEqual("Check now", self.text("#update-checked [data-check]"))
            self.assertFalse(self.present("#update-row [data-check]"), "the button is in its own row")
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "idle"}}):
            self.assertEqual("19-11-2026 11:42. " + QUIET, self.text("#update-checked p"))
        for _ in self.each({**BASE, "latest": {"state": "looking"}, "fetch": {"state": "idle"}}):
            self.assertEqual("Not checked yet.", self.text("#update-checked p"))
            self.assertEqual("Check now", self.text("#update-checked [data-check]"))

    def test_row_2_check_now_in_the_row_asks_the_server_to_look(self):
        self.load()
        self.replies(status=OK({**BASE, "latest": AVAIL, "fetch": {"state": "idle"}}), check=OK({"ok": True}))
        self.mount()
        self.click("#update-checked [data-check]")
        self.assertEqual(["status", "check", "status"], self.calls())

    def test_row_3_use_a_file_instead_row_has_its_text_review_and_choose_zip(self):
        for _ in self.each({**BASE, "available": {"version": "0.3.1", "label": "Review 0.3.1"}}):
            self.assertEqual("Use a file instead", self.text("#update-file-l"))
            self.assertEqual("For a computer with no internet. Review a clark download you already have.", self.text("#update-file-hint"))
            self.assertEqual(["Review", "Choose zip…"], self.val("[...document.querySelectorAll('#update-file button')].map(b => b.textContent)"))
            self.assertFalse(self.present("#update-row [data-review]"))
        for _ in self.each({**BASE}):
            self.assertEqual(["Choose zip…"], self.val("[...document.querySelectorAll('#update-file button')].map(b => b.textContent)"))

    def test_row_4_the_installed_row_has_its_title_text_and_undo(self):
        last = {"from": "0.3.0", "to": "0.3.1", "line": "Last update: 0.3.0 → 0.3.1 on 01-11-2026."}
        for _ in self.each({**BASE, "last": last}):
            self.assertEqual("Updated to clark 0.3.1", self.text("#update-last-l"))
            self.assertEqual("clark restarted and kept everything. If something looks wrong you can go back to 0.3.0.", self.text("#update-last p"))
            self.assertEqual("Undo update", self.text("#update-last [data-undo]"))
        for _ in self.each({**BASE, "last": {"line": "Last update: x."}}):
            self.assertEqual("Last update", self.text("#update-last-l"))
            self.assertEqual("x.", self.text("#update-last p"))

    def test_row_5_the_update_row_says_the_latest_sentence_with_the_day_word(self):
        for _ in self.each({**BASE, "latest": {"state": "latest", "checked": f"{self.today()} 11:42"}, "fetch": {"state": "idle"}}):
            self.assertEqual("Update", self.text("#update-row-l"))
            self.assertEqual("You have the latest version (0.3.0). Last checked today 11:42.", self.text("#update-line"))
            self.assertEqual("Today 11:42. " + QUIET, self.text("#update-checked p"))
            self.assertEqual(1, self.val("document.querySelectorAll('#update [data-check]').length"))

    def test_row_6_titles_that_stay(self):
        for _ in self.each({**BASE, "last": {"line": "Last update: x."}}):
            self.assertEqual(["Installed", "Update", "Use a file instead", "Last update"], self.val(LABELS))

    def test_row_7_offline_shows_the_server_sentence_and_try_again(self):
        for _ in self.each({**BASE, "latest": {"state": "offline", "message": OFFLINE, "checked": "19-11-2026 11:42"}, "fetch": {"state": "idle"}}):
            self.assertEqual("Update", self.text("#update-row-l"))
            self.assertEqual(OFFLINE, self.text("#update-line"))
            self.assertEqual("Try again", self.text("#update-row [data-check]"))
            self.assertFalse(self.present("#update-checked"))

    def test_row_8_a_failed_check_has_its_title_text_and_download_again(self):
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "failed", "version": "0.3.2", "message": FAILED}}):
            self.assertEqual("The download failed its check", self.text("#update-row-l"))
            self.assertEqual(FAILED, self.text("#update-line"))
            self.assertEqual("Download again", self.text("#update-row [data-download]"))
        for _ in self.each({**BASE, "latest": AVAIL, "fetch": {"state": "failed", "version": "0.3.2", "message": "The check did not finish. Try again."}}):
            self.assertEqual("Update", self.text("#update-row-l"), "only a failed check takes the failed-check title")

    def test_a_server_that_does_not_look_online_shows_neither_new_row(self):
        for _ in self.each({**BASE}):
            self.assertEqual(["Installed", "Update", "Use a file instead"], self.val(LABELS))


if __name__ == "__main__":
    unittest.main()
