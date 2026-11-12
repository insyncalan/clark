"""Mutation-kill tests for src/clark/setup_mode.py, plus hostile folder answers (the answer of the folder window is untrusted text).
Temporary home and folders only; the folder window is a fake. Run from tests/: python3 -m unittest test_setup_mode_mutants"""
import os
import unittest
from pathlib import Path
from unittest import mock

from test_setup_mode import Case

from clark import doctor, setup_mode


class Mutants(Case):
    def test_an_empty_list_of_checks_is_used_as_given_not_replaced_by_the_doctors(self):
        report = self.setup(checks=()).report()
        self.assertEqual(report["checks"], [])
        self.assertTrue(report["ready"])

    def test_an_empty_environ_is_passed_on_and_does_not_fall_back_to_the_real_one(self):
        env = {}
        self.assertIs(self.setup(environ=env).seen().environ, env)

    def test_no_environ_at_all_means_the_real_one(self):
        self.assertIs(self.setup(environ=None).seen().environ, os.environ)

    def test_a_path_of_exactly_the_limit_is_taken_and_one_more_is_not(self):
        base = str(self.good) + "/"
        ok = Path(base + "a" * (setup_mode.MAX_PATH - len(base)))
        self.assertEqual(len(str(ok)), setup_mode.MAX_PATH)
        self.assertEqual(setup_mode._plain_path(str(ok)), ok)
        self.assertIsNone(setup_mode._plain_path(str(ok) + "a"))

    def test_the_window_is_free_again_after_a_cancel_and_after_an_error(self):
        service = self.setup(answer=None)
        self.assertIsNone(service.choose("x"))
        self.assertIsNone(service.choose("x"))
        service = self.setup(answer=RuntimeError("window"))
        for _ in range(2):
            with self.assertRaises(RuntimeError):
                service.choose("x")

    def test_a_falsy_but_present_answer_is_checked_not_treated_as_cancel(self):
        for answer in ("", 0, b"", []):
            service = self.setup(answer=answer)
            with self.assertRaises(setup_mode.Refused) as raised:
                service.choose("x")
            self.assertEqual(raised.exception.code, "folder_refused", repr(answer))
            self.assertFalse(self.pointer().exists())

    def test_a_good_answer_keeps_the_pointer_and_moves_the_folder_in_use(self):
        service = self.setup(answer=self.good)
        report = service.choose("x")
        self.assertEqual(Path(service.folder), self.good.resolve())
        self.assertEqual(self.pointer().read_text(encoding="utf-8"), str(self.good.resolve()) + "\n")
        self.assertTrue(report["ok"])

    def test_remembered_ignores_whitespace_around_the_line_and_a_missing_pointer(self):
        service = self.setup()
        self.assertIsNone(service.remembered())
        self.pointer().write_text("  " + str(self.good) + " \n\n", encoding="utf-8")
        self.assertEqual(service.remembered(), self.good.resolve())


class Hostile(Case):
    def refused(self, answer):
        service = self.setup(answer=answer)
        with self.assertRaises(setup_mode.Refused) as raised:
            service.choose("x")
        self.assertEqual(raised.exception.code, "folder_refused", repr(answer))
        self.assertFalse(self.pointer().exists(), repr(answer))
        return raised.exception

    def test_text_that_is_not_an_absolute_folder_is_refused_in_words_that_name_nothing(self):
        secret = "SECRET-NAME"
        for bad in ("", " ", secret, "~/" + secret, "../" + secret, "./" + secret, "a" * 5000, "\x00" + str(self.good),
                    str(self.good) + "\n", str(self.good) + "\x00x", "\x1b[31m" + str(self.good), str(self.good) + "\x7f",
                    "\t" + str(self.good)):
            e = self.refused(bad)
            self.assertEqual(e.words, setup_mode.WORDS["not_a_folder"], repr(bad)[:40])
            self.assertNotIn(secret, e.words)

    def test_things_that_are_not_text_are_refused(self):
        for bad in (123, 1.5, True, ["/tmp"], {"a": 1}, b"/tmp", object()):
            self.assertEqual(self.refused(bad).words, setup_mode.WORDS["not_a_folder"], repr(bad))

    def test_a_file_a_missing_folder_and_a_link_are_refused_and_nothing_is_kept(self):
        a_file = self.home / "file.txt"
        a_file.write_text("x", encoding="utf-8")
        link = self.home / "link"
        link.symlink_to(self.good)
        for bad in (a_file, self.home / "nope", link):
            self.refused(bad)
        self.assertEqual(list(self.good.iterdir()), [])

    def test_a_folder_inside_onedrive_is_refused(self):
        inside = self.onedrive / "sub"
        inside.mkdir()
        self.refused(inside)

    def test_a_folder_that_cannot_be_written_in_is_refused(self):
        with mock.patch.object(doctor, "_can_save_in", return_value=False):
            e = self.refused(self.good)
        self.assertTrue(e.words)

    def test_a_pointer_holding_hostile_content_is_ignored_not_trusted(self):
        service = self.setup()
        for raw in (b"", b"\n", b"relative/path", b"\x00", b"a" * 5000, str(self.home / "gone").encode(),
                    str(self.good).encode() + b"\x00", b"\xff\xfe\x00bad"):
            self.pointer().write_bytes(raw)
            self.assertIsNone(service.remembered(), repr(raw)[:30])

    def test_a_pointer_that_is_a_folder_is_ignored(self):
        self.pointer().mkdir()
        self.assertIsNone(self.setup().remembered())

    def test_a_pointer_that_cannot_be_made_is_cant_save_and_leaves_the_folder_alone(self):
        blocker = self.home / "blocker"
        blocker.write_text("x", encoding="utf-8")
        service = self.setup(answer=self.good, pointer=lambda: blocker / "inside" / "ptr")
        before = service.folder
        with self.assertRaises(setup_mode.Refused) as raised:
            service.choose("x")
        self.assertEqual((raised.exception.code, raised.exception.words), ("cant_save", setup_mode.WORDS["cant_save"]))
        self.assertEqual(service.folder, before)


if __name__ == "__main__":
    unittest.main()
