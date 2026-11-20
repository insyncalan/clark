"""#1366 slice (d): pictures (PNG, JPG, JPEG) in the index. Made-up files and a made-up reader only: no real text recognition runs here.
Approved words: '1 picture read on this Mac.' / 'N pictures read on this Mac.'; '1 is a picture and this computer cannot read pictures.' /
'N are pictures and this computer cannot read them.'; the per-file reason 'is a picture and this computer cannot read pictures'.
Run: python3 dev/run_tests.py test_ask_index_pictures_1366"""
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401

from test_ask_index_1366 import FAKE_KEY, Base, ix
from clark import ask_index, ask_picture, platform as pl


def fake_reader(raw):
    if raw.startswith(b"BAD"):
        raise ask_picture.PictureUnreadable("damaged")
    return raw.decode("latin-1").split("|", 1)[-1]


class Pictures(Base):
    def setUp(self):
        super().setUp()
        p = mock.patch.object(ask_picture, "_READER", None)        # on a Mac ask_index registers the real reader at import: these tests start with none
        p.start()
        self.addCleanup(p.stop)

    def reader(self, on=pl.MAC, fn=fake_reader):
        for p in (mock.patch.object(ask_picture.platform, "system", return_value=on), mock.patch.object(ask_picture, "_READER", fn)):
            p.start()
            self.addCleanup(p.stop)

    def counts(self):
        return ix.status(self.data, "P1", [self.box])

    def test_where_no_reader_exists_every_picture_is_left_out_and_counted(self):
        for n in ("a.png", "b.jpg", "c.JPEG"):
            self.put(n, b"IMG|zqpicone", binary=True)
        self.put("t.txt", "zqtext")
        self.build()
        c = self.counts()
        self.assertEqual((c["indexed"], c["picture"], c["type"], c["pictures_read"]), (1, 3, 0, 0))
        self.assertEqual(ask_index.line_for(c), "Indexed 1 of 4 files. 3 are pictures and this computer cannot read them.")
        self.assertFalse(self.found("zqpicone"))

    def test_off_a_mac_a_registered_reader_is_not_offered(self):
        with mock.patch.object(ask_picture, "_READER", fake_reader):
            with mock.patch.object(ask_picture.platform, "system", return_value="linux"):
                self.assertIsNone(ask_picture.reader())
            with mock.patch.object(ask_picture.platform, "system", return_value=pl.MAC):
                self.assertIs(ask_picture.reader(), fake_reader)

    def test_off_a_mac_the_folder_line_says_the_picture_cannot_be_read(self):
        self.put("a.png", b"IMG|zqpicone", binary=True)
        with mock.patch.object(ask_picture, "reader", return_value=None):
            self.build()
        c = self.counts()
        self.assertEqual((c["indexed"], c["picture"]), (0, 1))
        self.assertEqual(ask_index.line_for(c), "Indexed 0 of 1 file. 1 is a picture and this computer cannot read pictures.")

    def test_on_a_mac_pictures_are_read_found_and_counted(self):
        self.reader()
        self.put("a.png", b"IMG|zqpicone words", binary=True)
        self.put("b.jpg", b"IMG|zqpictwo words", binary=True)
        self.build()
        self.assertEqual(len(self.found("zqpicone")), 1)
        self.assertIn("a.png", self.found("zqpicone")[0][0])
        c = self.counts()
        self.assertEqual((c["indexed"], c["picture"], c["pictures_read"]), (2, 0, 2))
        self.assertEqual(ask_index.line_for(c), "Indexed 2 of 2 files. 2 pictures read on this Mac.")

    def test_one_picture_read_says_picture(self):
        self.reader()
        self.put("a.png", b"IMG|zqpicone", binary=True)
        self.build()
        self.assertEqual(ask_index.line_for(self.counts()), "Indexed 1 of 1 file. 1 picture read on this Mac.")

    def test_a_picture_text_that_looks_like_a_key_is_screened(self):
        self.reader()
        self.put("a.png", b"IMG|" + FAKE_KEY.encode(), binary=True)
        self.build()
        c = self.counts()
        self.assertEqual((c["indexed"], c["safety"], c["pictures_read"]), (0, 1, 0))
        self.assertFalse(self.found("hunter2"))

    def test_a_picture_the_reader_cannot_read_is_a_type_not_an_error(self):
        self.reader()
        self.put("a.png", b"BAD", binary=True)
        self.build()
        c = self.counts()
        self.assertEqual((c["indexed"], c["type"], c["picture"]), (0, 1, 0))

    def test_counts_add_up_to_the_files_in_the_folder(self):
        self.put("a.png", b"IMG|x", binary=True)
        self.put("b.jpeg", b"IMG|y", binary=True)
        self.put("t.txt", "zqtext")
        self.put("z.bin", b"\0", binary=True)
        self.put("keys.txt", FAKE_KEY)
        for mac in (False, True):
            if mac:
                self.reader()
            self.build()
            c = self.counts()
            self.assertEqual(sum(c[k] for k in ask_index.NAMES), 5, c)
            per = ask_index.folder_status(self.data, "P1", [self.box])[str(self.box)]
            self.assertTrue(per["line"].startswith("Indexed"))

    def test_the_left_out_list_names_the_picture_with_the_approved_reason(self):
        self.put("a.png", b"IMG|x", binary=True)
        self.build()
        out = ask_index.files_left_out(self.data, "P1", 200)
        self.assertEqual(out["files"], [("saved/a.png", "is a picture and this computer cannot read pictures")])

    def test_a_reader_that_appears_later_reads_the_unchanged_picture_again(self):
        self.put("a.png", b"IMG|zqlater", binary=True)
        self.build()
        self.assertEqual(self.counts()["picture"], 1)
        self.reader()
        ix.refresh(self.data, "P1", [self.box])
        self.assertEqual((self.counts()["picture"], self.counts()["pictures_read"]), (0, 1))
        self.assertTrue(self.found("zqlater"))

    def test_a_picture_left_out_is_not_stale_every_time(self):
        self.put("a.png", b"IMG|x", binary=True)
        self.build()
        self.assertFalse(ask_index.stale(self.data, "P1", [self.box]))

    def test_the_count_words_for_one_and_many(self):
        self.assertEqual(ask_index.left_out_line("picture", 1), "1 is a picture and this computer cannot read pictures.")
        self.assertEqual(ask_index.left_out_line("picture", 4), "4 are pictures and this computer cannot read them.")

    def test_a_picture_over_the_size_limit_counts_too_long_when_read(self):
        self.reader()
        self.put("a.png", b"IMG|x", binary=True)
        with mock.patch.object(ask_picture, "MAX_PICTURE_BYTES", 2):
            self.build()
        self.assertEqual((self.counts()["too_long"], self.counts()["pictures_read"]), (1, 0))


if __name__ == "__main__":
    unittest.main()
