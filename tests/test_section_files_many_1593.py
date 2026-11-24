"""Row 1593: several files added at once to a Documents and links section, by the file window and by drop (server side).

The file window: the system's dialog is stubbed (platform.choose_open_files is a seam on the publisher), so no dialog is ever shown;
the stub returns the list and the rows must come in that order. The drop: one request per file (25 MB stays per file) with the hold
header, then one commit that adds every held file in one step. Either way: each file is judged on its own and a refused file has its
own problem line "{file name}: {reason}"; the section's 20-entry limit holds across the batch; one apply_id, so one Undo takes the
whole batch off (the copies stay in the client folder). The width and theme checks of the page are in the browser tests, which are
not part of this file.

Run: python3 dev/run_tests.py test_section_files_many_1593
Fictional data only; temporary folders.
"""
import json
import unittest
from urllib.parse import quote

import test_section_file_route as base
from test_server import chrome  # noqa: F401  (this file builds on a browser test module, so the tier test files it as a browser-tier file by this import)
from clark import publish_flow, section_files, to_client
from clark.section_kinds import doclinks
from _demo import USER

PDF = base.PDF
SENTENCE = "That type of file can't be added. Use PDF, Word, Excel, PowerPoint, JPG, PNG or TXT."


class Many(base.Route):
    def setUp(self):
        super().setUp()
        self.ref = self.section()
        self.picked = []
        self.dialogs = []
        self.pub = publish_flow.Publisher(self.s.path, [], fs=to_client.RealFs(), choose_open_file=self.choose,
                                          choose_open_files=self.choose_many, by_user=lambda: USER, data_dir=self.data,
                                          today=lambda: "2030-01-15")

    def choose_many(self, prompt, types=None):
        self.dialogs.append((prompt, types))
        if not self.picked:                         # the tests inherited from the one-file route choose the one file their way
            one = self.pub.choose_open_file(prompt, types=types)
            return [one] if one else None
        return self.picked

    def make(self, *names, data=PDF):
        out = []
        for n in names:
            p = self.src / n
            p.write_bytes(data + n.encode())
            out.append(p)
        return out

    def mark(self):
        return self.s.con.execute("SELECT coalesce(max(rowid), 0) FROM change_log").fetchone()[0]

    def names(self):
        return [i["name"] for i in (self.items(self.ref) or {"items": []})["items"]]

    def drop_batch(self, files, ref=None):
        """What the page does for several dropped files: a hold per file, then one commit. Returns (held names, lines, commit reply)."""
        ref = ref or self.ref
        held, lines = [], []
        for name, data in files:
            status, body = self.pub.drop_section_file("ABC", ref, quote(name, safe=""), data, "1")
            if status == 200:
                held.append(body["held"]["name"])
            else:
                lines.append(body["message"])
        reply = self.pub.drop_section_file("ABC", ref, "", b"", None, quote(json.dumps(held), safe="")) if held else None
        return held, lines, reply

    # AP1
    def test_the_file_window_adds_every_chosen_file_in_order(self):
        self.picked = self.make("Zeta.pdf", "Alpha.pdf", "Mid.pdf")
        status, body = self.attach(self.ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.dialogs, [(section_files.PROMPT, doclinks.ALLOWED_ENDINGS)])
        self.assertEqual(self.names(), ["Zeta.pdf", "Alpha.pdf", "Mid.pdf"], "the rows are in the order the dialog returned")
        self.assertEqual(body["message"], "3 files added.")
        self.assertEqual(body["problems"], [])

    # AP2
    def test_a_drop_of_several_files_is_added_like_the_file_window(self):
        held, lines, reply = self.drop_batch([("One.pdf", PDF), ("Two.pdf", PDF + b"2"), ("Three.pdf", PDF + b"3")])
        self.assertEqual((held, lines), (["One.pdf", "Two.pdf", "Three.pdf"], []))
        status, body = reply
        self.assertEqual(status, 200, body)
        self.assertEqual(self.names(), ["One.pdf", "Two.pdf", "Three.pdf"])
        self.assertEqual((body["message"], body["problems"]), ("3 files added.", []))
        self.assertEqual(self.files(), ["One.pdf", "Three.pdf", "Two.pdf"])
        self.assertEqual((self.client / "Report files" / "Two.pdf").read_bytes(), PDF + b"2")

    # AP3
    def test_a_refused_file_is_named_and_the_others_are_added(self):
        self.picked = self.make("Plan.pdf", "tool.exe", "Budget.pdf")
        status, body = self.attach(self.ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.names(), ["Plan.pdf", "Budget.pdf"])
        self.assertEqual(body["problems"], [f"tool.exe: {SENTENCE}"])
        self.assertEqual(body["message"], "2 files added.")
        self.assertEqual(self.files(), ["Budget.pdf", "Plan.pdf"], "the refused file was never copied")
        # the same through a drop
        held, lines, reply = self.drop_batch([("Other.pdf", PDF), ("run.sh", PDF), ("Big.pdf", PDF + b"x")])
        self.assertEqual(held, ["Other.pdf", "Big.pdf"])
        self.assertEqual(lines, [f"run.sh: {SENTENCE}"])
        self.assertEqual(reply[0], 200, reply)
        self.assertEqual(self.names()[-2:], ["Other.pdf", "Big.pdf"])
        # nothing usable: refused whole, every file named, nothing written
        self.picked = self.make("a.exe", "b.zip")
        written = self.snapshot()
        status, body = self.attach(self.ref)
        self.assertEqual((status, body["ok"], body["problems"]), (409, False, [f"a.exe: {SENTENCE}", f"b.zip: {SENTENCE}"]))
        self.assertEqual(self.snapshot(), written)
        self.assertNotIn("apply_id", body, "when nothing is added there is no Undo")

    # AP4
    def test_the_twenty_entry_limit_holds_across_a_batch(self):
        self.picked = self.make(*[f"Old {n:02}.pdf" for n in range(18)])
        status, body = self.attach(self.ref)
        self.assertEqual((status, len(self.names())), (200, 18), body)
        self.picked = self.make("New 1.pdf", "New 2.pdf", "New 3.pdf", "New 4.pdf")
        status, body = self.attach(self.ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.names()[18:], ["New 1.pdf", "New 2.pdf"], "the files that fit are added, in order")
        self.assertEqual(body["problems"], [f"New 3.pdf: {doclinks.TOO_MANY}", f"New 4.pdf: {doclinks.TOO_MANY}"])
        self.assertEqual(body["message"], "2 files added.")
        self.assertNotIn("New 3.pdf", self.files(), "a file left out is not copied and left behind")
        before = self.files()
        self.picked = self.make("Last.pdf")                 # full: the early refusal before the dialog stays
        self.dialogs.clear()
        status, body = self.attach(self.ref)
        self.assertEqual((status, body["code"], body["message"]), (409, "full", doclinks.TOO_MANY))
        self.assertEqual((self.dialogs, self.files()), ([], before))

    # AP5
    def test_one_undo_takes_the_whole_batch_off(self):
        self.picked = self.make("A.pdf", "B.pdf", "bad.exe")
        mark = self.mark()
        status, body = self.attach(self.ref)
        self.assertEqual(status, 200, body)
        events = self.s.con.execute("SELECT apply_id FROM change_log WHERE rowid > ?", (mark,)).fetchall()
        self.assertTrue(events, "the batch wrote events")
        self.assertEqual({r[0] for r in events}, {body["apply_id"]}, "every event of the batch carries the one apply_id")
        status, undone = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, undone)
        self.assertEqual(self.names(), [], "every file of the batch is off the section")
        self.assertEqual(self.files(), ["A.pdf", "B.pdf"], "the copies stay in the client folder")
        # one file in the batch: today's toast words, one Undo
        self.picked = self.make("Only.pdf")
        status, body = self.attach(self.ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["message"], section_files.ADDED.format(name="Only.pdf"))
        # a drop: the commit is the one step
        mark = self.mark()
        _held, _lines, reply = self.drop_batch([("D1.pdf", PDF), ("D2.pdf", PDF)])
        status, body = reply
        self.assertEqual(self.s.con.execute("SELECT count(DISTINCT apply_id) FROM change_log WHERE rowid > ?", (mark,)).fetchone()[0], 1,
                         "the drop's commit is one apply_id over all its events")
        self.assertEqual(self.undo({"project": "ABC", "apply_id": body["apply_id"]})[0], 200)
        self.assertEqual(self.names(), ["Only.pdf"])

    def test_a_commit_names_only_files_already_held_and_judged(self):
        self.drop_batch([("Real.pdf", PDF)])
        for names in (["../x.pdf"], ["Ghost.pdf"], ["Real.pdf", "Real.pdf"], [], "Real.pdf"):
            status, body = self.pub.drop_section_file("ABC", self.ref, "", b"", None, quote(json.dumps(names), safe=""))
            self.assertNotEqual(status, 200, (names, body))
        (self.client / "Report files" / "Fake.pdf").write_bytes(b"not a pdf")
        status, body = self.pub.drop_section_file("ABC", self.ref, "", b"", None, quote(json.dumps(["Fake.pdf"]), safe=""))
        self.assertEqual((status, body["problems"]), (409, [f"Fake.pdf: {SENTENCE}"]))

    def test_the_25_mb_limit_stays_per_file(self):
        big = PDF + b"x" * (section_files.MAX_FILE_BYTES - len(PDF) - 10)
        files = [(f"Big {n}.pdf", big) for n in range(3)]
        held, lines, reply = self.drop_batch(files)
        self.assertEqual((len(held), lines, reply[0]), (3, [], 200), reply)
        self.assertEqual(len(self.names()), 3, "three files of nearly 25 MB are not refused whole")

    def commit(self, *names):
        return self.pub.drop_section_file("ABC", self.ref, "", b"", None, quote(json.dumps(list(names)), safe=""))

    def test_a_held_file_changed_before_the_commit_is_refused_at_the_commit(self):
        held = []
        for name in ("Grown.pdf", "Swapped.pdf", "Linked.pdf", "Fine.pdf"):      # the holds only: nothing is committed yet
            status, body = self.pub.drop_section_file("ABC", self.ref, quote(name, safe=""), PDF, "1")
            self.assertEqual(status, 200, body)
            held.append(body["held"]["name"])
        self.assertEqual((held, self.names()), (["Grown.pdf", "Swapped.pdf", "Linked.pdf", "Fine.pdf"], []))
        folder = self.client / "Report files"
        with open(folder / "Grown.pdf", "r+b") as f:
            f.truncate(section_files.MAX_FILE_BYTES + 1)           # a sparse file over 25 MB
        (folder / "Swapped.pdf").unlink()
        (folder / "Swapped.pdf").mkdir()                           # a directory in its place
        (folder / "Linked.pdf").unlink()
        (folder / "Linked.pdf").symlink_to(folder / "Fine.pdf")    # a link in its place
        status, body = self.commit(*held)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.names(), ["Fine.pdf"], "only the file still ordinary and within 25 MB is added")
        self.assertEqual(sorted(p.split(":")[0] for p in body["problems"]), ["Grown.pdf", "Linked.pdf", "Swapped.pdf"])


if __name__ == "__main__":
    unittest.main()
