"""Pins for survivors of a hand-made mutation sweep of publish_pdf.py (seven small changes the existing tests did not notice).
Each test fails on the mutant named in its docstring and passes on the real module. Fictional data only.

Run: python3 dev/run_tests.py test_publish_pdf_mut
"""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import _paths  # noqa: F401

from clark import pdf_text, publish, publish_pdf, to_client


class Fs:
    def __init__(self, entries):
        self.entries = entries

    def listdir(self, folder):
        return self.entries


LONG_FOLDER = "/" + "/".join(["a" * 40] * 5)           # about 205 characters: the name must be cut to fit under the path limit


class SplitPins(unittest.TestCase):
    def test_a_pdf_value_that_is_not_true_does_not_switch_the_pdf_on(self):
        """Mutant: `on` = bool(body.get("pdf")). A loose value is an error AND is not read as ticked."""
        for loose in ("yes", 1, "true", [1]):
            req, _ = publish_pdf.split({"pdf": loose})
            self.assertFalse(req["on"], loose)
            self.assertEqual(req["error"], "bad_pdf_request", loose)
        self.assertTrue(publish_pdf.split({"pdf": True})[0]["on"])
        self.assertFalse(publish_pdf.split({"pdf": False})[0]["on"])


class FooterPins(unittest.TestCase):
    def test_the_publication_number_starts_at_one(self):
        """Mutants: number >= 0, number > 1."""
        self.assertEqual(publish_pdf.footer_text("2026-10-28", 1), "Publication 1 · 28-10-2026")
        self.assertEqual(publish_pdf.footer_text("2026-10-28", 0), "Published 28-10-2026")
        self.assertEqual(publish_pdf.footer_text("2026-10-28", -3), "Published 28-10-2026")


class ProblemsPins(unittest.TestCase):
    def check(self, data, text="All fine."):
        with mock.patch.object(pdf_text, "text_of", return_value=text):
            return publish_pdf.problems(data, [])

    def test_the_size_limit_is_exactly_max_bytes(self):
        """The limit is exactly MAX_BYTES (a mutant of > MAX_BYTES + 1 is equivalent: to_client.check_copy repeats the same guard)."""
        self.assertEqual(self.check(b"x" * publish.MAX_BYTES), [])
        self.assertEqual(self.check(b"x" * (publish.MAX_BYTES + 1)), ["a file over the size limit"])

    def test_a_three_letter_word_that_is_not_in_the_report_is_an_extra_word(self):
        """Mutant: WORD = words of four letters or more."""
        self.assertEqual(publish_pdf.extra_words("the zqx", b"<p>the</p>"), ["zqx"])
        self.assertEqual(publish_pdf.extra_words("ab", b"<p>the</p>"), [], "two letters are not a word")


class DetailsPins(unittest.TestCase):
    def test_words_in_the_pdfs_details_are_not_held_to_the_reports_words(self):
        """Mutant: the added-words check reads the details as well as the pages (Chrome's own Producer would stop every PDF)."""
        data = b"%PDF-1.4\n1 0 obj<</Producer (Zzzqword Writer)>>endobj\n"
        with mock.patch.object(pdf_text, "text_of", return_value="Harbour survey"):
            self.assertEqual(publish_pdf.problems(data, [], None, b"<p>Harbour survey</p>"), [])
            self.assertEqual(publish_pdf.problems(data, [], None, b"<p>Harbour</p>"), [publish_pdf.EXTRA_WORDS], "a page word is checked")

    def test_a_missing_or_empty_folder_is_not_looked_for_in_the_text(self):
        """Mutant: the folder test loses `if folder and` (None becomes the text 'None', empty matches everything)."""
        with mock.patch.object(pdf_text, "text_of", return_value="None of the actions are late"):
            self.assertEqual(publish_pdf.problems(b"%PDF", [], None), [])
            self.assertEqual(publish_pdf.problems(b"%PDF", [], ""), [])

    def test_details_of_reads_a_byte_order_mark_as_two_bytes_and_joins_with_new_lines(self):
        """Mutants: the UTF-16 test looks at one byte only; the details are joined with nothing."""
        self.assertEqual(publish_pdf.details_of(b"/Title (\xfeAB)"), "\xfeAB", "not a byte order mark: read as plain text")
        self.assertEqual(publish_pdf.details_of(b"/Title (One) /Author (Two)"), "One\nTwo")


class FinishPins(unittest.TestCase):
    def step(self, **kw):
        base = dict(on=True, data=b"%PDF", pub=object(), kept_all=True, kept_local=True, local=Path("r.pdf"), store=None, seq=None)
        base.update(kw)
        step = SimpleNamespace(**base)
        step.write = mock.Mock(return_value=["PDF saved."])
        return step

    def test_a_reply_that_is_not_a_200_saves_no_pdf_even_if_it_says_ok(self):
        """Mutant: finish reads only out["ok"] and not the status."""
        step = self.step()
        out = {"ok": True, "message": "Published."}
        publish_pdf.finish(step, out, 500)
        step.write.assert_not_called()
        self.assertEqual(out, {"ok": True, "message": "Published."})

    def test_the_row_is_named_only_when_the_publish_was_recorded_in_one(self):
        """Mutant: record_pdf_name is called with seq None."""
        store = mock.Mock()
        publish_pdf.finish(self.step(store=store, seq=None), {"ok": True, "message": "m"}, 200)
        store.record_pdf_name.assert_not_called()
        out = {"ok": True, "message": "m"}
        publish_pdf.finish(self.step(store=store, seq=7), out, 200)
        store.record_pdf_name.assert_called_once_with(7, "r.pdf")
        self.assertEqual(out["pdf_name"], "r.pdf")


class ClientFolderPins(unittest.TestCase):
    def test_a_client_folder_that_cannot_be_opened_says_so_not_cancelled(self):
        """Mutant: the unreadable-folder stop gives the Cancel message."""
        class Broken:
            def listdir(self, folder):
                raise OSError("denied")
        req = publish_pdf.split({})[0]
        kind, message = publish_pdf.client_name(Broken(), "/c", "x.html", False, req)
        self.assertEqual(kind, "stop")
        self.assertIn("could not be opened", message)
        self.assertNotEqual(message, to_client.MESSAGES["cancelled"])


class LongFolderPins(unittest.TestCase):
    def test_a_typed_pdf_name_is_cut_to_fit_the_clients_folder_path(self):
        """Mutant: rename_target drops `folder` when the typed name already ends .pdf."""
        typed = "w" * 100 + ".pdf"
        short = publish_pdf.rename_target(typed)
        cut = publish_pdf.rename_target(typed, LONG_FOLDER)
        self.assertEqual(short, typed)
        self.assertTrue(cut.endswith(".pdf"))
        self.assertLess(len(cut), len(short))

    def test_a_numbered_pdf_name_is_cut_to_fit_the_clients_folder_path(self):
        """Mutant: client_name calls numbered_name without the folder."""
        name = "r" * 100 + ".html"
        taken = Fs([{"name": publish_pdf.pdf_name(name), "kind": "file"}])
        req = publish_pdf.split({"pdf_on_clash": "number"})[0]
        got = publish_pdf.client_name(taken, LONG_FOLDER, name, False, req)
        self.assertEqual(got[0], "write")
        self.assertTrue(got[1].endswith(" (2).pdf"))
        self.assertLess(len(got[1]), len(publish_pdf.pdf_name(name)) + len(" (2)"), "cut to leave room in a long path")


if __name__ == "__main__":
    unittest.main()
