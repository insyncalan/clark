"""#96 R2: POST /api/section-file {project, section}, a file for a Documents and links or One document section.

The system's Open dialog (platform.choose_open_file, a seam here), the copy into the client folder's "Report files" folder (a
safe name, never overwriting: a number is added; a temporary file then a link into place), and the entry {name, rel, bytes} added
to the section in one step with one Undo. Every refusal is plain words with the next step and writes nothing: no client folder
(the dialog never opens), a folder clark may not use, a section that holds no file or is full, a file from a place clark never
reads, a folder or a file too big, "Report files" that is not a real folder. Undo takes the file off the section and leaves it in
the folder; a step that fails takes back the copy it made. Through the real server: the token, and the route's 1 KB limit. The
file's name never reaches the day's log.

Run: python3 dev/run_tests.py test_section_file_route
Fictional data only; temporary folders; no dialog is ever shown.
"""
import json
import os
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from clark import changes, log as clark_log, page, platform, publish_flow, section_files, server as sv, to_client
from clark.section_kinds import doclinks
from test_report_editor import EMPTY_BRANDING, Base as PageBase
from test_server import Running, chrome

PDF = b"%PDF-1.4 fictional plan\n" * 50


class Route(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(platform, "system", return_value=platform.MAC)      # reach's never-read list is Mac-only: the tests say they are on a Mac (as test_reach does), so they run alike on Linux CI
        patch.start()
        self.addCleanup(patch.stop)
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-96-r2-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.data = self.tmp / "data"
        self.data.mkdir()
        self.client = self.tmp / "Client share"
        self.client.mkdir()
        self.src = self.tmp / "papers"
        self.src.mkdir()
        self.source = self.src / "Plan v2.pdf"
        self.source.write_bytes(PDF)
        self.demo.update("projects", "ABC", {"publish_client": str(self.client)})
        self.chosen = [self.source]
        self.asked = []
        self.pub = publish_flow.Publisher(self.s.path, [], fs=to_client.RealFs(), choose_open_file=self.choose,
                                          by_user=lambda: USER, data_dir=self.data, today=lambda: "2030-01-15")
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)

    def choose(self, prompt, start=None):
        self.asked.append(prompt)
        return self.chosen[0]

    def section(self, kind="doclinks", title="Fictional papers"):
        status, body = self.change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": kind, "title": title}, "after": None})
        self.assertEqual(status, 200, body)
        return body["ref"]

    def items(self, ref):
        text = self.s.read("report_sections", ref=ref)["body"]
        return json.loads(text) if text else None

    def files(self):
        folder = self.client / "Report files"
        return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else (None if not folder.exists() else "a file")

    def snapshot(self):
        con = sqlite3.connect(str(self.s.path))
        try:
            return (con.execute("SELECT count(*) FROM applies").fetchone()[0], con.execute("SELECT count(*) FROM change_log").fetchone()[0])
        finally:
            con.close()

    def attach(self, ref, project="ABC"):
        return self.pub.section_file({"project": project, "section": ref})

    def refused(self, ref, code, status=409, dialog=True, **kw):
        before, files = self.snapshot(), self.files()
        got = self.pub.section_file({"project": kw.get("project", "ABC"), "section": ref})
        self.assertEqual((got[0], got[1]["ok"], got[1]["code"]), (status, False, code), got)
        self.assertEqual(self.snapshot(), before, "nothing was written to the store")
        self.assertEqual(self.files(), files, "nothing was written to the client folder")
        self.assertEqual(bool(self.asked), dialog, "the dialog opened" if dialog else "the dialog never opened")
        message = got[1]["message"]
        self.assertFalse(message.startswith("clark"), "a message never starts with the product name")
        self.assertNotIn(str(self.tmp), message, "no folder is named in full")
        return message

    # ── the copy and the step ──────────────────────────────────────────────

    def test_the_file_is_copied_and_added_in_one_step_and_undo_leaves_the_copy(self):
        ref = self.section()
        status, body = self.attach(ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.asked, [section_files.PROMPT])
        self.assertEqual(self.files(), ["Plan v2.pdf"])
        self.assertEqual((self.client / "Report files" / "Plan v2.pdf").read_bytes(), PDF)
        entry = {"name": "Plan v2.pdf", "rel": "Report files/Plan v2.pdf", "bytes": len(PDF)}
        self.assertEqual(body["file"], entry)
        self.assertEqual(self.items(ref), {"v": 1, "items": [{"kind": "file", **entry, "label": ""}]})
        self.assertIn("“Plan v2.pdf” was copied into the client folder's “Report files” folder and added.", body["message"])
        self.assertTrue(all("body" not in r for r in body["sections"]), "the reply never carries a body")
        fields = self.s.con.execute("SELECT field FROM change_log WHERE apply_id = ? AND field != 'updated_at'", (body["apply_id"],)).fetchall()
        self.assertEqual([r["field"] for r in fields], ["body"])
        status, done = self.undo({"project": "ABC", "apply_id": body["apply_id"]})
        self.assertEqual(status, 200, done)
        self.assertIn(self.s.read("report_sections", ref=ref)["body"], ("", None))
        self.assertEqual(self.files(), ["Plan v2.pdf"], "Undo never deletes a client's file")
        self.assertFalse(list((self.client / "Report files").glob(".*.part")), "no temporary file is left")

    def test_a_taken_name_gets_a_number_and_nothing_is_overwritten(self):
        ref = self.section()
        self.attach(ref)
        (self.client / "Report files" / "Plan v2 (2).pdf").write_bytes(b"someone else's")
        self.source.write_bytes(PDF + b"v3")
        status, body = self.attach(ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["file"]["name"], "Plan v2 (3).pdf")
        self.assertEqual(self.files(), ["Plan v2 (2).pdf", "Plan v2 (3).pdf", "Plan v2.pdf"])
        self.assertEqual((self.client / "Report files" / "Plan v2.pdf").read_bytes(), PDF)
        self.assertEqual((self.client / "Report files" / "Plan v2 (2).pdf").read_bytes(), b"someone else's")
        self.assertEqual([i["name"] for i in self.items(ref)["items"]], ["Plan v2.pdf", "Plan v2 (3).pdf"])

    def test_a_name_is_made_safe_for_sharepoint(self):
        ref = self.section()
        odd = self.src / ".Q3 plan: final?.pdf"
        odd.write_bytes(PDF)
        self.chosen = [odd]
        status, body = self.attach(ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["file"]["name"], "Q3 plan- final-.pdf")
        self.assertEqual(doclinks.file_name(body["file"]["name"]), "Q3 plan- final-.pdf")

    def test_a_hidden_device_name_is_not_left_as_a_device_name(self):
        for odd in (".CON.pdf", "..nul.txt", ". Com1.pdf", ".aux"):
            ref = self.section()
            f = self.src / odd
            f.write_bytes(PDF)
            self.chosen = [f]
            status, body = self.attach(ref)
            self.assertEqual(status, 200, body)
            stem = body["file"]["name"].split(".")[0].rstrip(" ").upper()
            self.assertNotIn(stem, platform.RESERVED_NAMES, body["file"]["name"])
            self.assertFalse(body["file"]["name"].startswith("."))

    def test_one_document_takes_the_file_in_place_of_the_last_one(self):
        ref = self.section("onedoc", "Fictional document")
        self.change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "place": "report",
                     "changes": {"body": json.dumps({"v": 1, "label": "The signed plan", "text": ["Signed."]})}})
        self.attach(ref)
        other = self.src / "Plan v3.pdf"
        other.write_bytes(PDF)
        self.chosen = [other]
        status, body = self.attach(ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.items(ref), {"v": 1, "label": "The signed plan", "text": ["Signed."],
                                           "file": {"name": "Plan v3.pdf", "rel": "Report files/Plan v3.pdf", "bytes": len(PDF)}})
        self.assertEqual(self.files(), ["Plan v2.pdf", "Plan v3.pdf"])

    def test_a_file_already_in_report_files_is_used_where_it_is(self):
        ref = self.section()
        (self.client / "Report files").mkdir()
        there = self.client / "Report files" / "Budget.xlsx"
        there.write_bytes(b"fictional budget")
        self.chosen = [there]
        status, body = self.attach(ref)
        self.assertEqual(status, 200, body)
        self.assertEqual(self.files(), ["Budget.xlsx"])
        self.assertIn("already in the client folder's “Report files” folder", body["message"])

    def test_cancel_changes_nothing(self):
        ref = self.section()
        before = self.snapshot()
        self.chosen = [None]
        self.assertEqual(self.attach(ref), (200, {"ok": True, "cancelled": True}))
        self.assertEqual(self.snapshot(), before)
        self.assertIsNone(self.files(), "the folder is not even made")

    def test_a_failed_step_takes_back_the_copy_it_made(self):
        ref = self.section()
        self.pub.add_section_file = lambda req: (400, {"ok": False, "code": "refused", "message": "That content is too long to save."})
        status, body = self.attach(ref)
        self.assertEqual(status, 400)
        self.assertEqual(self.files(), [], "the copy this request made is gone")
        self.assertIn(self.s.read("report_sections", ref=ref)["body"], ("", None))

    def test_a_replaced_file_is_left_alone_when_the_step_fails(self):
        ref = self.section()
        target = self.client / "Report files" / "Plan v2.pdf"

        def fails(req):
            target.unlink()
            target.write_bytes(b"someone else's, put there since")
            return 400, {"ok": False, "code": "refused", "message": "That content is too long to save."}
        self.pub.add_section_file = fails
        status, body = self.attach(ref)
        self.assertEqual(status, 400)
        self.assertEqual(target.read_bytes(), b"someone else's, put there since")

    # ── refusals before the dialog ─────────────────────────────────────────

    def test_no_client_folder_says_where_to_set_it_and_never_opens_the_dialog(self):
        ref = self.section()
        self.demo.update("projects", "ABC", {"publish_client": None})
        message = self.refused(ref, "no_client_folder", dialog=False)
        self.assertEqual(message, "This project has no client folder yet, so the file has nowhere to go. Choose one in Settings, "
                                  "under Publishing, then add the file again.")

    def test_a_client_folder_that_is_gone_or_clark_s_own_is_refused(self):
        ref = self.section()
        shutil.rmtree(self.client)
        message = self.refused(ref, "client_folder_refused", dialog=False)
        self.assertTrue(message.startswith("The folder “Client share” isn't there.") and message.endswith("Then add the file again."), message)
        self.demo.update("projects", "ABC", {"publish_client": str(self.data / "inside")})
        (self.data / "inside").mkdir()
        self.refused(ref, "client_folder_refused", dialog=False)

    def test_a_section_that_holds_no_file_another_project_s_and_a_bad_request(self):
        text = self.section("text", "Fictional notes")
        card = self.section("linkcard", "Fictional card")
        self.assertEqual(self.refused(text, "no_file_here", 400, dialog=False), changes.NO_FILE_HERE)
        self.refused(card, "no_file_here", 400, dialog=False)
        self.refused("ABC-S-999", "section_gone", 404, dialog=False)
        self.refused(text, "project_not_found", 404, dialog=False, project="XYZ")
        for bad in ({}, {"project": "ABC"}, {"project": "ABC", "section": text, "file": "/etc/hosts"}, [], "x",
                    {"project": "abc", "section": text}, {"project": "ABC", "section": "../x"}, {"project": "ABC", "section": 7}):
            with self.subTest(bad=bad):
                status, body = self.pub.section_file(bad)
                self.assertEqual((status, body["ok"]), (400, False), body)
        self.assertEqual(self.asked, [])

    def test_a_full_section_is_refused_before_the_dialog(self):
        ref = self.section()
        full = [{"kind": "link", "href": f"https://example.org/{n}", "label": ""} for n in range(doclinks.MAX_ITEMS)]
        self.change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "place": "report",
                     "changes": {"body": json.dumps({"v": 1, "items": full})}})
        self.assertEqual(self.refused(ref, "full", dialog=False), doclinks.TOO_MANY)

    def test_an_archived_project_is_read_only(self):
        ref = self.section()
        with self.s.step("dashboard", USER) as st:
            st.archive("projects", "ABC")
        self.refused(ref, "archived", dialog=False)

    def test_one_at_a_time(self):
        ref = self.section()
        self.pub.lock.acquire()
        try:
            self.refused(ref, "busy", dialog=False)
        finally:
            self.pub.lock.release()

    # ── refusals after the dialog ──────────────────────────────────────────

    def test_a_file_from_a_place_clark_never_reads_is_not_copied(self):
        ref = self.section()
        secret = self.data / "clark.db"
        secret.write_bytes(b"fictional database")
        link = self.src / "harmless.pdf"
        os.symlink(secret, link)
        for chosen in (secret, link, self.src / ".ssh" / "id_rsa"):
            with self.subTest(chosen=chosen.name):
                if chosen.name == "id_rsa":
                    chosen.parent.mkdir()
                    chosen.write_bytes(b"fictional key")
                self.asked.clear()
                self.chosen = [chosen]
                self.refused(ref, "never_place")

    def test_a_folder_a_missing_file_and_a_file_too_big(self):
        ref = self.section()
        self.chosen = [self.src]
        self.refused(ref, "not_a_file")
        self.asked.clear()
        self.chosen = [self.src / "gone.pdf"]
        self.refused(ref, "unreadable")
        self.asked.clear()
        self.chosen = [self.source]
        with mock.patch.object(section_files, "MAX_FILE_BYTES", len(PDF) - 1):
            message = self.refused(ref, "too_big")
        self.assertIn("add a link to it instead", message)

    def test_report_files_must_be_a_real_folder_in_the_client_folder(self):
        ref = self.section()
        (self.client / "Report files").write_bytes(b"a file, not a folder")
        self.refused(ref, "files_folder")
        (self.client / "Report files").unlink()
        outside = self.tmp / "elsewhere"
        outside.mkdir()
        os.symlink(outside, self.client / "Report files")
        self.asked.clear()
        before = self.snapshot()
        got = self.attach(ref)
        self.assertEqual((got[0], got[1]["code"]), (409, "files_folder"))
        self.assertEqual(list(outside.iterdir()), [], "nothing is written through a link out of the client folder")
        self.assertEqual(self.snapshot(), before)

    def test_a_dialog_that_fails_says_so(self):
        ref = self.section()

        def broken(prompt, start=None):
            self.asked.append(prompt)
            raise platform.PlatformError("The file window could not be opened. " + platform.TRY_AGAIN)
        self.pub.choose_open_file = broken
        self.assertEqual(self.refused(ref, "dialog_failed"), "The file window could not be opened. " + platform.TRY_AGAIN)

    # ── through the server ─────────────────────────────────────────────────

    def test_through_the_server_the_token_and_the_size_are_checked_and_the_log_names_no_file(self):
        ref = self.section()
        folder = self.tmp / "logs"
        handler = clark_log.install(clark_log.Log(folder))
        self.addCleanup(lambda: __import__("logging").getLogger("clark").removeHandler(handler))
        server = Running(publisher=self.pub)
        self.addCleanup(server.close)
        req = json.dumps({"project": "ABC", "section": ref}).encode("utf-8")
        status, _, data = server.api("POST", "/api/section-file", req, token="not the token")
        self.assertEqual(status, 403)
        self.assertEqual(self.asked, [])
        status, _, data = server.api("POST", "/api/section-file", json.dumps({"project": "ABC", "section": ref, "x": "y" * 2048}).encode("utf-8"))
        self.assertEqual((status, json.loads(data)["code"]), (400, "too_large"))
        status, _, data = server.api("POST", "/api/section-file", req)
        self.assertEqual(status, 200, data)
        self.assertEqual(json.loads(data)["file"]["name"], "Plan v2.pdf")
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/section-file"], 1024)
        logged = "".join(p.read_text(encoding="utf-8") for p in folder.glob("*.log")) if folder.exists() else ""
        for marker in ("Plan v2", "Client share", "papers", str(self.tmp)):
            self.assertNotIn(marker, logged)


class InThePage(PageBase):
    """Edit's Add a file and Choose the file… through the real route: the list redraws from the store, the toast says what was
    copied and offers Undo, and a refusal is said in the route's own words."""

    def setUp(self):
        super().setUp()
        patch = mock.patch.object(platform, "system", return_value=platform.MAC)      # reach's never-read list is Mac-only: the tests say they are on a Mac (as test_reach does), so they run alike on Linux CI
        patch.start()
        self.addCleanup(patch.stop)
        self.s.close()
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-96-r2-page-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "data").mkdir()
        self.client = self.tmp / "Client share"
        self.client.mkdir()
        self.source = self.tmp / "Plan v2.pdf"
        self.source.write_bytes(PDF)
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"publish_client": str(self.client)})
        self.pub = publish_flow.Publisher(self.store.path, [], fs=to_client.RealFs(), choose_open_file=lambda prompt, start=None: self.source,
                                          by_user=lambda: USER, data_dir=self.tmp / "data", today=lambda: "2030-01-15")
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING),
                         change=self.seam(self.real_change, "change"), undo=self.seam(self.real_undo, "undo"), publisher=self.pub)
        self.addCleanup(self.s.close)

    def add(self, kind):
        with self.store.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": kind, "title": f"Fictional {kind}", "sort_order": 999})

    def test_add_a_file_copies_it_draws_it_and_undo_takes_it_off(self):
        ref = self.add("doclinks")
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-add-file]')", "the Edit part drew")
            self.assertEqual(p.js(f"document.querySelector('{sel} [data-add-file]').textContent"), "Add a file…")
            p.js(f"document.querySelector('{sel} [data-add-file]').click()")
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 1", "the file is drawn")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-name').textContent"), "Plan v2.pdf")
            self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-facts').textContent"), "2 KB")
            p.until("!!document.querySelector('[data-undo]')", "the toast offers Undo")
            self.assertIn("was copied into the client folder", p.js("document.querySelector('.toast').textContent"))
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 0", "Undo took it off")
            self.assertEqual(sorted(x.name for x in (self.client / "Report files").iterdir()), ["Plan v2.pdf"])

    def test_one_document_and_no_client_folder_said_in_the_route_s_words(self):
        ref = self.add("onedoc")
        sel = f"[data-id={json.dumps(ref)}]"
        with self.store.step("dashboard", USER) as st:
            st.update("projects", "ABC", {"publish_client": None})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.until(f"!!document.querySelector('{sel} [data-add-file]')", "the Edit part drew")
            self.assertEqual(p.js(f"document.querySelector('{sel} [data-add-file]').textContent"), "Choose the file…")
            p.js(f"document.querySelector('{sel} [data-add-file]').click()")
            p.until("!!document.querySelector('.toast') && document.querySelector('.toast').textContent.includes('no client folder')", "the refusal")
            self.assertIn(section_files.MESSAGES["no_client_folder"], p.js("document.querySelector('.toast').textContent"))
            self.assertFalse(p.js("!!document.querySelector('[data-undo]')"), "nothing to undo")


class OpenDialog(unittest.TestCase):
    """platform.choose_open_file: the system's own Open dialog, given its words as arguments, never inside the script."""

    def run_with(self, code, out="", err=""):
        calls = []

        def run(args, **kw):
            calls.append(args)
            return mock.Mock(returncode=code, stdout=out, stderr=err)
        return calls, run

    def test_the_prompt_and_the_start_are_arguments_and_cancel_is_none(self):
        calls, run = self.run_with(0, "/Users/someone/Plan.pdf\n")
        self.assertEqual(platform.choose_open_file("Pick “it”; end run", start="/tmp", run=run, on=platform.MAC), Path("/Users/someone/Plan.pdf"))
        args = calls[0]
        self.assertEqual(args[:2], ["osascript", "-e"])
        self.assertIn("choose file with prompt (item 1 of argv)", args[2])
        self.assertNotIn("Pick", args[2])
        self.assertEqual(args[3:], ["Pick “it”; end run", "/tmp"])
        calls, run = self.run_with(1, err="execution error: User canceled. (-128)")
        self.assertIsNone(platform.choose_open_file("Pick", run=run, on=platform.MAC))
        calls, run = self.run_with(1, err="something else")
        with self.assertRaises(platform.PlatformError) as e:
            platform.choose_open_file("Pick", run=run, on=platform.MAC)
        self.assertEqual(str(e.exception), "The file window could not be opened. " + platform.TRY_AGAIN)

    def test_windows_is_not_built_yet(self):
        with self.assertRaises(platform.NotBuiltYet):
            platform.choose_open_file("Pick", run=lambda *a, **k: None, on=platform.WINDOWS)


if __name__ == "__main__":
    unittest.main()
