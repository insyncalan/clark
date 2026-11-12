"""Row 1077, HOSTILE (guarded PR 1255): a published file carries a row's Source by NAME only (source_name.py is the one character
allow-list). Every other route into the bytes is tried with planted markers: a folder, a user name, a host name, an internal note,
markup. Real publish runs (the Rig of test_publish_route: a real server over a real store, nothing leaves the machine, no Chrome),
the finished bytes scanned in every spelling: the web file, the client copy, the Word copy (every part of the zip), the print
preview (what the PDF is made from), and every file the run left on the disk but the database.

Routes: a hand-edited item (writer), the Excel import (file named like a path), the Word import (file and heading), a copy of an item,
a rename of the source after a publish, an old published file kept in the folder, the activity (history) lines, the Needs-from-client
rows, the milestone Source line and the JSON data block.

Run: python3 dev/run_tests.py test_hostile_1077
"""
import base64
import datetime
import html
import json
import re
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.parse import quote

from _paths import SRC  # noqa: F401  (first: puts src/ on the path)
import _publish_fixture as fx
from clark import activity_read, changes, excel, word_route
from clark import excel_import as xi
from clark.source_name import source_name
from openpyxl import load_workbook
from test_docx_read import P, docx
from test_publish_route import USER, WANTED, Rig

DIR, WHO, HOST, FOLDER, NOTE, MARKUP = ("ZQ-DIR-3301", "zquser7712", "zq-host-4410.example.com", "ZQ-PRIVATE-FOLDER-5512",
                                        "ZQ-NOTE-8820", "ZQ-MARKUP-9931")
KEEP = "ZQ-KEEP-6001.xlsx"                      # a file NAME may be shown
MARKERS = (DIR, WHO, HOST, FOLDER, NOTE, MARKUP)
HOSTILE = (
    f"/Users/{WHO}/{DIR}/{KEEP}",
    f"C:\\Users\\{WHO}\\{FOLDER}\\{KEEP}",
    f"\\\\{HOST}\\share\\{DIR}\\{KEEP}",
    f"https://{HOST}/{DIR}/{KEEP}?u={WHO}",
    f"https://{HOST}#{KEEP}",
    f"//{HOST}?{DIR}#{KEEP}",
    f"{WHO}@{HOST}",
    f"{WHO}@{HOST}:{DIR}/{KEEP}",
    f"Macintosh HD:Users:{WHO}:{FOLDER}:{KEEP}",
    f"Macintosh HD:Users:{WHO}:{FOLDER}",
    f"%2FUsers%2F{WHO}%2F{DIR}%2F{KEEP}",
    f"%252FUsers%252F{WHO}%252F{DIR}%252F{KEEP}",
    f"&#47;Users&#47;{WHO}&#47;{DIR}&#47;{KEEP}",
    f"&amp;#47;Users&amp;#47;{WHO}{DIR}",
    f"Excel import, 2026-10-01, /Users/{WHO}/{DIR}/{KEEP}",
    f"~{WHO}/{DIR}/{KEEP}",
    f"file:///Users/{WHO}/{DIR}/{KEEP}",
    f"\uff0fUsers\uff0f{WHO}\uff0f{DIR}\uff0f{KEEP}",
    f"x<script>{MARKUP}</script>{KEEP}",
    f"<img src=x onerror=alert(1)>{MARKUP}</b>",
    f"{DIR}\u202e/{KEEP}",
    f"{WHO}\x00/{DIR}/{KEEP}",
)


def spells(marker):
    return fx.spellings(marker) + [quote(marker), quote(marker, safe="")]


def haystacks(data):
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else data
    return (text, text.lower(), html.unescape(text).lower())


def word_parts(path):
    with zipfile.ZipFile(path) as z:
        return b"\n".join(z.read(n) for n in z.namelist())


class Hostile(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-hostile-1077-")).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def leaks(self, data, markers=MARKERS):
        found = []
        for hay in haystacks(data):
            for m in markers:
                for s in spells(m):
                    if s in hay or s.lower() in hay:
                        found.append(s)
        return sorted(set(found))

    def assert_clean(self, where, data, markers=MARKERS):
        self.assertEqual(self.leaks(data, markers), [], f"{where} holds a planted marker")

    def plant_rows(self, sources):
        """One action, risk, decision and milestone per hostile source; the writer, past the change route."""
        made = []
        with self.rig.store.step("dashboard", USER) as st:
            for i, src in enumerate(sources):
                a = st.create("actions", {"project": "PUB", "description": f"Hostile action {i}", "raised": "2026-10-20", "source": src})
                r = st.create("raid", {"project": "PUB", "type": "Risk", "description": f"Hostile risk {i}", "raised": "2026-10-20", "source": src})
                d = st.create("decisions", {"project": "PUB", "decision": f"Hostile decision {i}", "status": "Pending", "source": src})
                m = st.create("milestones", {"project": "PUB", "name": f"Hostile milestone {i}", "baseline_date": "2026-12-01", "source": src})
                made += [("actions", a), ("raid", r), ("decisions", d), ("milestones", m)]
            for table, ref in made:
                if table == "milestones":                          # the one table with an internal note
                    st.update(table, ref, {"internal_note": NOTE})
        return made

    def publish_all(self, word=True):
        """The web file (local and client copy), the Word copy, the print preview, and every file left on the disk but the database."""
        status, got = self.rig.publish(to_client=True, on_clash="overwrite", confirmed=True, print=True)
        self.assertEqual((status, got["ok"]), (200, True), got)
        out = {"web": (self.rig.local / "chosen.html").read_bytes(), "client copy": (self.rig.client / WANTED).read_bytes()}
        if got.get("print_url"):
            status, preview = self.rig.call("GET", got["print_url"])
            if status == 200 and isinstance(preview, (bytes, str)):
                out["print preview"] = preview if isinstance(preview, bytes) else preview.encode("utf-8")
        if word:
            seam = word_route.make_word_export(self.rig.db, [], USER, today=lambda: "2026-10-28",
                                               choose_folder=lambda prompt: str(self.rig.local))
            status, got = seam({"project": "PUB", "to_client": True, "on_clash": "overwrite", "confirmed": True})
            self.last_word = (status, got)
        for rel in self.rig.everything_written():
            path = self.rig.root / rel
            if path.suffix.lower() == ".docx":
                out["disk " + rel] = word_parts(path)
            elif path.suffix.lower() not in (".png", ".jpg", ".pdf"):
                out["disk " + rel] = path.read_bytes()
        return out

    def data_block(self, web):
        text = web.decode("utf-8")
        m = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S)
        self.assertTrue(m, "the file has its data block")
        return json.loads(m.group(1))


class HandEdited(Hostile):
    def test_no_hostile_source_reaches_any_published_byte_through_a_hand_edited_item(self):
        self.plant_rows(HOSTILE)
        for where, data in self.publish_all().items():
            self.assert_clean(where, data)

    def test_each_hostile_source_is_in_the_data_block_as_a_clean_name_or_nothing(self):
        self.plant_rows(HOSTILE)
        block = self.data_block(self.publish_all(word=False)["web"])
        rows = block["data"] if "data" in block else block
        seen = 0
        for table in ("actions", "raid", "decisions", "milestones"):
            for row in rows[table]:
                if "Hostile" not in json.dumps(row):
                    continue
                shown = row.get("source")
                seen += 1
                self.assertTrue(shown is None or isinstance(shown, str), row)
                for ch in "/\\<>@%~|":
                    self.assertNotIn(ch, shown or "", (table, row.get("id"), shown))
        self.assertGreaterEqual(seen, 4 * len(HOSTILE))

    def test_a_marker_that_is_a_file_name_is_the_one_thing_shown(self):
        """Not vacuous: the file name of the first path does reach the file, and nothing in front of it."""
        self.plant_rows(HOSTILE[:1])
        web = self.publish_all(word=False)["web"].decode("utf-8")
        self.assertIn(KEEP, web)
        self.assertNotIn(f"{DIR}/{KEEP}", web)

    def test_the_internal_note_of_the_same_row_stays_out(self):
        self.plant_rows((KEEP,))
        for where, data in self.publish_all().items():
            self.assert_clean(where, data, (NOTE,))

    def test_the_change_route_cannot_set_a_source_or_a_path_that_it_sets_is_still_clean(self):
        change = changes.make_change(self.rig.db, [], USER)
        ref = self.rig.store.read("actions", "PUB")[0]["id"]
        before = self.rig.store.read("actions", ref=ref)["source"]
        status, got = change({"project": "PUB", "kind": "actions", "op": "update", "id": ref, "changes": {"source": f"/Users/{WHO}/{DIR}/{KEEP}"}})
        after = self.rig.store.read("actions", ref=ref)["source"]
        if status == 200 and after != before:
            for where, data in self.publish_all().items():
                self.assert_clean(where, data)
        else:
            self.assertEqual(after, before)


class Imports(Hostile):
    def excel_import(self, file_name):
        path = self.tmp / file_name
        state = self.tmp / "state.json"
        excel.export_project(self.rig.store, "PUB", path, state, on="2026-10-28")
        wb = load_workbook(str(path))
        ws = wb["Actions"]
        head = [c.value for c in ws[1]]
        row = [None] * len(head)
        for key, value in {"Description": "Imported hostile action", "Raised": datetime.date(2026, 10, 20), "Owner": "Sam", "Client-visible": "Yes"}.items():
            row[head.index(key)] = value
        ws.append(row)
        wb.save(str(path))
        plan = xi.read_workbook(self.rig.store, path, "PUB", state_path=state)
        plan.accept_all()
        result = xi.apply_import(self.rig.store, plan, USER, state_path=state)
        self.assertTrue(result.applied, result)
        return [r["source"] for r in self.rig.store.read("actions", "PUB") if r["description"] == "Imported hostile action"][0]

    def test_an_excel_import_of_a_file_named_like_a_path_publishes_no_part_of_the_path(self):
        for name in (f"C:\\Users\\{WHO}\\{FOLDER}\\{KEEP}", f"Macintosh HD:Users:{WHO}:{FOLDER}:{KEEP}", f"{WHO}@{HOST}.xlsx", f"{DIR}\\{KEEP}"):
            stored = self.excel_import(name)
            self.assertTrue(stored.startswith("Excel import"), stored)
            self.tmp = Path(tempfile.mkdtemp(prefix="clark-hostile-1077-")).resolve()     # a fresh folder: the same export is not imported twice
            self.addCleanup(shutil.rmtree, self.tmp, True)
        for where, data in self.publish_all().items():
            self.assert_clean(where, data)

    def test_a_word_import_with_a_path_for_a_file_name_and_for_a_heading_publishes_no_part_of_it(self):
        word_route.PLANS.clear()
        self.addCleanup(word_route.PLANS.clear)
        seam = word_route.make_word_import(self.rig.db, [], USER, today=lambda: "2026-10-28", clock=lambda: 1000.0)
        for i, (name, heading) in enumerate(((f"/Users/{WHO}/{DIR}/notes.docx", f"Next steps in /Users/{WHO}/{FOLDER}/{KEEP}"),
                                              (f"C:\\Users\\{WHO}\\{FOLDER}\\notes.docx", f"{WHO}@{HOST}"),
                                              (f"Macintosh HD:Users:{WHO}:{FOLDER}:notes.docx", f"Macintosh HD:Users:{WHO}:{FOLDER}"))):
            body = P("Notes", style="Heading1") + P(heading, style="Heading1") + P(f"Chase the supplier {i}") + P("Risks", style="Heading1") + P(f"Supplier may slip {i}")
            status, got = seam({"op": "check", "project": "PUB", "name": name, "data": base64.b64encode(docx(body)).decode("ascii")})
            self.assertEqual(status, 200, got)
            status, got = seam({"op": "apply", "project": "PUB", "plan": got["plan"], "accept": "all"})
            self.assertEqual(status, 200, got)
        imported = [r["source"] for t in ("actions", "raid", "decisions") for r in self.rig.store.read(t, "PUB") if (r["source"] or "").startswith("Word import")]
        self.assertTrue(imported, "the import made rows")
        for where, data in self.publish_all().items():
            self.assert_clean(where, data)


class FreeText(Hostile):
    def test_free_text_with_no_separator_reaches_no_file_but_the_file_name_does(self):
        self.plant_rows((f"Word import, 2026-11-11, {KEEP}, under {WHO} is underperforming", f"Raised by {DIR} about {FOLDER}"))
        web = self.publish_all(word=False)["web"].decode("utf-8")
        self.assertIn(KEEP, web)
        for where, data in self.publish_all().items():
            self.assert_clean(where, data, (WHO, DIR, FOLDER))


class AfterPublish(Hostile):
    def test_a_copy_of_an_item_and_a_rename_of_the_source_after_a_publish_leave_no_path_in_any_file(self):
        made = self.plant_rows((f"/Users/{WHO}/{DIR}/{KEEP}",))
        for where, data in self.publish_all().items():
            self.assert_clean(where, data)
        change = changes.make_change(self.rig.db, [], USER)
        status, got = change({"project": "PUB", "kind": "actions", "op": "new", "copy_of": made[0][1], "values": {"description": "A copy"}})
        self.assertEqual(status, 200, got)
        with self.rig.store.step("dashboard", USER) as st:             # the rename: the folder is renamed, the stored words are edited
            for table, ref in made:
                st.update(table, ref, {"source": f"\\\\{HOST}\\{FOLDER}\\{WHO}\\{KEEP}"})
        for where, data in self.publish_all().items():
            self.assert_clean(where, data)

    def test_an_old_published_file_kept_in_the_folder_is_never_rewritten_and_the_kept_copies_are_clean(self):
        old = self.rig.client / "PUB-report-2026-10-16.html"
        old.write_bytes(b"<html>an earlier file, as the owner left it</html>")
        stamp = old.read_bytes()
        self.plant_rows(HOSTILE)
        for where, data in self.publish_all().items():
            self.assert_clean(where, data)
        self.assertEqual(old.read_bytes(), stamp, "an old file in the folder is not touched")


class Lines(Hostile):
    def test_the_activity_line_shows_the_name_only_and_the_published_file_carries_neither_the_person_nor_a_path(self):
        who = "Zq Personone"
        with self.rig.store.step("dashboard", who) as st:
            ref = st.create("actions", {"project": "PUB", "description": "Made by a named person", "raised": "2026-10-20",
                                        "source": f"/Users/{WHO}/{DIR}/{KEEP}"})
        line = activity_read.source_line(self.rig.store.con, ref, [{"op": activity_read.OP_MADE, "ref": ref, "table": "actions", "by_user": who}])
        for part in (DIR, WHO, "/"):
            self.assertNotIn(part, line, "the live Source line is the name too")
        for where, data in self.publish_all().items():
            self.assert_clean(where, data, MARKERS + ("Zq Personone",))

    def test_needs_from_client_rows_and_the_milestone_source_line_carry_the_name_only(self):
        with self.rig.store.step("dashboard", USER) as st:
            a = st.create("actions", {"project": "PUB", "description": "Needs a client answer", "raised": "2026-10-20", "owner": "Client lead",
                                      "source": f"C:\\Users\\{WHO}\\{FOLDER}\\{KEEP}"})
            m = st.create("milestones", {"project": "PUB", "name": "A milestone with a path source", "baseline_date": "2026-12-01",
                                         "source": f"https://{HOST}/{DIR}/{KEEP}"})
        got = self.publish_all(word=False)
        rows = json.dumps(self.data_block(got["web"]))
        self.assertIn(a, rows)
        self.assertIn(m, rows)
        for where, data in got.items():
            self.assert_clean(where, data)


class TheAllowList(unittest.TestCase):
    """The unit answer for every shape above, so a change to source_name.py shows here at once."""

    def test_no_marker_survives_source_name_whatever_the_shape(self):
        for stored in HOSTILE:
            shown = source_name(stored, published=True)
            for m in MARKERS:
                self.assertNotIn(m.lower(), shown.lower(), (stored, shown))
            self.assertFalse(set(shown) & set("/\\<>@%~|"), (stored, shown))

    def test_ordinary_words_are_still_shown_whole_in_the_live_peek(self):
        for words in ("Steering minutes", "Plan: v2", "Excel import, 12:30, plan.xlsx", "R&D notes", "C# review", "Workshop (second)"):
            self.assertEqual(source_name(words), words)

    def test_free_text_never_publishes_only_a_file_name_does(self):
        """Ruling A of row 1077: the Source line in a file is the file name, free text dropped."""
        for words in ("Steering minutes", "Plan: v2", "R&D notes", "Added by hand in clark", f"Raised by {WHO}, {NOTE} is underperforming"):
            self.assertEqual(source_name(words, published=True), "", words)
        self.assertEqual(source_name(f"Word import, 2026-11-11, {KEEP}, under {WHO} is underperforming", published=True), KEEP)
        self.assertEqual(source_name(f"Word import, 2026-11-11, under {WHO} is underperforming", published=True), "")
        self.assertEqual(source_name(f"Word import, 2026-11-11, {KEEP}", published=True), KEEP)
        self.assertEqual(source_name(KEEP, published=True), KEEP)


if __name__ == "__main__":
    unittest.main()
