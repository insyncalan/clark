"""#1292 S14: files added to a question, on the server (POST /api/ask with "files": [{name, data}], src/clark/ask_files.py).

Run: python3 dev/run_tests.py test_ask_files_route
A real server and store with a STUB provider (nothing here calls a model). Covers: a text, Markdown or CSV file is sent as a passage named by
its file name; a file with a key or a password line is refused before anything is sent; five files at most, 10 MB each; a name that is a path,
bytes that are not base64, a kind that cannot be read yet (PDF, Word, Excel, pictures: NEEDS RULING) and a wrong shape each say why and send
nothing; the files are not kept (no row written, no file on disk). Fictional text only.
"""
import base64
import os
import unittest

from test_ask_route import Base

MB = 1024 * 1024


def f(name, text=b"", raw=None):
    return {"name": name, "data": base64.b64encode(raw if raw is not None else text).decode()}


class Files(Base):
    def sent(self):
        return self.provider.sent

    def test_a_text_file_is_sent_as_a_passage_named_by_its_file(self):
        status, got = self.question("What does my note say?", files=[f("notes.txt", b"ZQ-FILE-LINE the vendor moved to March")])
        self.assertEqual(status, 200, got)
        (text,) = self.sent()
        self.assertIn("ZQ-FILE-LINE the vendor moved to March", text)
        self.assertIn("notes.txt", text)

    def test_markdown_and_csv_are_read_too(self):
        status, got = self.question(files=[f("a.md", b"# ZQ-MD-HEAD"), f("b.csv", b"id,ZQ-CSV-CELL\n1,2")])
        self.assertEqual(status, 200, got)
        self.assertIn("ZQ-MD-HEAD", self.sent()[0])
        self.assertIn("ZQ-CSV-CELL", self.sent()[0])

    def test_a_file_with_a_password_line_is_refused_and_nothing_is_sent(self):
        status, got = self.question(files=[f("ok.txt", b"fine"), f("conf.txt", b"db password: Hunter2xyz99!")])
        self.assertEqual(status, 400, got)
        self.assertEqual(got["code"], "refused")
        self.assertEqual(self.sent(), [])
        self.assertNotIn("Hunter2", got["message"])
        self.assertIn("conf.txt", got["message"])

    def test_a_private_key_block_is_refused(self):
        status, got = self.question(files=[f("k.txt", b"-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBg\n-----END PRIVATE KEY-----")])
        self.assertEqual(status, 400, got)
        self.assertEqual(self.sent(), [])

    def test_five_files_are_taken_six_are_not(self):
        five = [f("f%d.txt" % i, b"line %d" % i) for i in range(5)]
        self.assertEqual(self.question(files=five)[0], 200)
        status, got = self.question(files=five + [f("g.txt", b"x")])
        self.assertEqual(status, 400, got)
        self.assertEqual(len(self.sent()), 1)

    def test_ten_mb_is_the_most_for_a_file(self):
        status, got = self.question(files=[f("big.txt", raw=b"a " * (5 * MB) + b"a")])
        self.assertEqual(status, 400, got)
        self.assertIn("big.txt", got["message"])
        self.assertEqual(self.sent(), [])

    def test_a_name_that_is_a_path_is_refused(self):
        for name in ("../x.txt", "/etc/x.txt", "a\\b.txt", "~/x.txt", ""):
            status, got = self.question(files=[f(name, b"x")])
            self.assertEqual(status, 400, name)
        self.assertEqual(self.sent(), [])

    def test_bytes_that_are_not_base64_are_refused(self):
        status, got = self.question(files=[{"name": "a.txt", "data": "!!not base64!!"}])
        self.assertEqual(status, 400, got)
        self.assertEqual(self.sent(), [])

    def test_a_wrong_shape_is_refused(self):
        for bad in ("a.txt", [1], [{"name": "a.txt"}], [{"name": "a.txt", "data": "eA==", "x": 1}], {"name": "a.txt"}):
            status, got = self.question(files=bad)
            self.assertEqual(status, 400, bad)
        self.assertEqual(self.sent(), [])

    def test_a_kind_that_cannot_be_read_yet_says_so(self):          # NEEDS RULING: PDF, Word, Excel and pictures need a reader or the command's picture support
        for name in ("a.pdf", "a.docx", "a.xlsx", "a.png", "a.jpg"):
            status, got = self.question(files=[f(name, b"x")])
            self.assertEqual(status, 400, name)
            self.assertIn("cannot be read yet", got["message"], name)
            self.assertIn("Nothing was sent", got["message"], name)
        self.assertEqual(self.sent(), [])

    def test_an_empty_list_is_the_same_as_none(self):
        self.assertEqual(self.question(files=[])[0], 200)

    def test_the_gate_still_comes_first(self):
        self.set_switch(False)
        status, got = self.question(files=[f("a.txt", b"x")])
        self.assertEqual(status, 409, got)
        self.assertEqual(self.sent(), [])

    def test_nothing_is_kept(self):
        before = self.counts()
        self.question(files=[f("keep.txt", b"ZQ-NOT-KEPT")])
        self.assertEqual(self.counts(), before)
        for root, _dirs, names in os.walk(self.d):
            for n in names:
                self.assertNotEqual(n, "keep.txt")


if __name__ == "__main__":
    unittest.main()
