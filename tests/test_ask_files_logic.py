"""#1292 S14: files and pictures for the next question, the rules (src/clark/page/src/edit/askFiles.js).

Run: python3 dev/run_tests.py test_ask_files_logic
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skips without node). Fictional names only.
Covers: five files at most, 10 MB each (10 MB itself is taken), the kinds taken (text, Markdown, CSV, PDF, Word, Excel, PNG, JPEG),
a plain sentence for each refusal, the size shown as KB or MB, the same name twice, what is kept after a refusal, and the bin.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

EDIT = SRC / "clark" / "page" / "src" / "edit"
MB = 1024 * 1024


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "af.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AF", str(EDIT / "askFiles.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


def add(current, incoming):
    """current and incoming are lists of [name, size]."""
    cur = "[" + ",".join("{id:%d,name:%s,size:%d}" % (i + 1, json.dumps(n), s) for i, (n, s) in enumerate(current)) + "]"
    inc = "[" + ",".join("{name:%s,size:%d}" % (json.dumps(n), s) for n, s in incoming) + "]"
    return run_node("(function(){var r=AF.addFiles(%s,%s);return {names:r.files.map(function(f){return f.name}),notes:r.notes,kinds:r.files.map(function(f){return f.kind}),ids:r.files.map(function(f){return f.id})}})()" % (cur, inc))


class Limits(unittest.TestCase):
    def test_the_numbers(self):
        self.assertEqual(run_node("[AF.FILE_MAX, AF.FILE_BYTES]"), [5, 10 * MB])

    def test_ten_mb_exactly_is_taken_one_byte_more_is_not(self):
        self.assertEqual(add([], [("a.pdf", 10 * MB)])["names"], ["a.pdf"])
        got = add([], [("b.pdf", 10 * MB + 1)])
        self.assertEqual(got["names"], [])
        self.assertEqual(got["notes"], ["b.pdf is over 10 MB. Add a smaller one."])

    def test_five_are_taken_the_sixth_is_not_and_says_why(self):
        five = [("f%d.txt" % i, 10) for i in range(5)]
        got = add(five[:4], [("x.txt", 10), ("y.txt", 10)])
        self.assertEqual(got["names"], ["f0.txt", "f1.txt", "f2.txt", "f3.txt", "x.txt"])
        self.assertEqual(got["notes"], ["5 files at most for one question. Remove one first."])
        self.assertEqual(add(five, [("z.txt", 1)])["names"], [n for n, _ in five])

    def test_a_refused_file_does_not_stop_the_ones_after_it(self):
        got = add([], [("big.txt", 11 * MB), ("odd.exe", 5), ("ok.csv", 5)])
        self.assertEqual(got["names"], ["ok.csv"])
        self.assertEqual(len(got["notes"]), 2)

    def test_a_zero_byte_file_is_refused(self):
        got = add([], [("empty.txt", 0)])
        self.assertEqual(got["names"], [])
        self.assertEqual(got["notes"], ["empty.txt is empty. Add one with something in it."])

    # Killers (#1292 S14 mutation sweep)
    def test_the_limit_sentence_is_said_once_however_many_files_are_over(self):
        five = [("f%d.txt" % i, 10) for i in range(5)]
        got = add(five, [("x.txt", 10), ("y.txt", 10), ("z.txt", 10)])
        self.assertEqual(got["notes"], ["5 files at most for one question. Remove one first."])

    def test_an_empty_file_does_not_stop_the_ones_after_it(self):
        got = add([], [("empty.txt", 0), ("ok.txt", 5)])
        self.assertEqual(got["names"], ["ok.txt"])
        self.assertEqual(len(got["notes"]), 1)

    def test_a_refused_kind_does_not_stop_the_ones_after_it(self):
        got = add([], [("odd.exe", 5), ("ok.txt", 5)])
        self.assertEqual(got["names"], ["ok.txt"])

    def test_the_list_that_waits_is_not_changed_by_adding(self):
        got = run_node("(function(){var cur=[{id:1,name:'a.txt',size:5}];var r=AF.addFiles(cur,[{name:'b.txt',size:5}]);return {kept:cur.length,now:r.files.length}})()")
        self.assertEqual(got, {"kept": 1, "now": 2})

    def test_the_bytes_are_sent_whole_in_base64_even_past_one_chunk(self):
        import base64
        raw = bytes((i * 7 + i // 251) % 256 for i in range(100000))          # three chunks of 0x8000 and a rest, every byte value
        want = base64.b64encode(raw).decode()
        if not shutil.which("node"):
            self.skipTest("no node")
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "af.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=AF", str(EDIT / "askFiles.js"), f"--outfile={out}"], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            script = Path(tmp) / "probe.js"
            script.write_text(out.read_text(encoding="utf-8") + ";\nvar data=new Uint8Array(%s);AF.encodeFiles([{name:'x.bin',file:{arrayBuffer:function(){return Promise.resolve(data.buffer)}}}]).then(function(o){console.log(JSON.stringify(o))});" % json.dumps(list(raw)), encoding="utf-8")
            ran = subprocess.run([shutil.which("node"), str(script)], capture_output=True, text=True)
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertEqual(json.loads(ran.stdout), [{"name": "x.bin", "data": want}])


class Kinds(unittest.TestCase):
    def test_each_kind(self):
        names = ["a.txt", "b.MD", "c.csv", "d.pdf", "e.docx", "f.xlsx", "g.png", "h.JPG", "i.jpeg"]
        got = add([], [(n, 10) for n in names])
        self.assertEqual(got["names"], names[:5])        # five at most; the kinds are read below
        self.assertEqual(got["kinds"], ["text", "text", "text", "document", "document"])
        got = add([], [(n, 10) for n in names[5:]])
        self.assertEqual(got["kinds"], ["document", "picture", "picture", "picture"])

    def test_other_kinds_are_refused_in_plain_words(self):
        for name in ["run.exe", "a.zip", "noext", "x.txt.exe", "pic.gif", "old.doc"]:
            got = add([], [(name, 10)])
            self.assertEqual(got["names"], [], name)
            self.assertEqual(got["notes"], [name + " cannot be used. Add text, Markdown, CSV, PDF, Word, Excel, PNG or JPEG files."], name)

    def test_ids_are_new_and_never_repeat(self):
        got = add([("a.txt", 1), ("b.txt", 1)], [("c.txt", 1)])
        self.assertEqual(len(set(got["ids"])), 3)


class Size(unittest.TestCase):
    def test_size_text(self):
        got = run_node("[1,500,1024,1536,1048575,1048576,5*1048576+524288,10485760].map(AF.sizeText)")
        self.assertEqual(got, ["1 KB", "1 KB", "1 KB", "2 KB", "1024 KB", "1.0 MB", "5.5 MB", "10.0 MB"])


class Bin(unittest.TestCase):
    def test_remove_leaves_the_others_in_order(self):
        got = run_node("AF.removeFile([{id:1,name:'a'},{id:2,name:'b'},{id:3,name:'c'}],2).map(function(f){return f.name})")
        self.assertEqual(got, ["a", "c"])

    def test_remove_of_an_unknown_id_changes_nothing(self):
        self.assertEqual(run_node("AF.removeFile([{id:1,name:'a'}],9).length"), 1)


class Words(unittest.TestCase):
    def test_the_lines_the_mock_up_shows(self):
        got = run_node("[AF.SCREEN_LINE, AF.THIS_QUESTION_LINE, AF.ATTACH_LABEL, AF.REMOVE_FILE('a.txt'), AF.DROP_LINE]")
        self.assertEqual(got[0], "Screened for passwords and keys, then sent with your next question to Claude.")
        self.assertEqual(got[1], "Files you add are used for this question only and are not kept in the project.")
        self.assertEqual(got[2], "Add a file")
        self.assertEqual(got[3], "Remove a.txt")
        self.assertEqual(got[4], "Drop a file or picture to add it to your next question")

    def test_no_sentence_starts_with_the_product_name(self):
        got = run_node("[AF.SCREEN_LINE, AF.THIS_QUESTION_LINE, AF.ATTACH_LABEL, AF.DROP_LINE]")
        self.assertFalse([s for s in got if s.lower().startswith("clark")])


if __name__ == "__main__":
    unittest.main()
