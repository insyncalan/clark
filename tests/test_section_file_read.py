"""Row 1221: GET /api/section-file?project=<CODE>&name=<NAME>[&download=1], the editor View's Open and Download on a file row.

One path rule: the name is one file name (doclinks.file_name) and the project lists it in a Documents and links or One document
section; the file is then read from "Report files" in the client folder and nothing else is ever opened. A ../ path, an absolute
path, a name with a slash or a backslash is refused 400 (bad_file_name); a name the project does not list is 404 (file_not_listed),
whether or not a file of that name sits in the folder. No refusal names a folder. A listed name is served: Open inline, Download
(download=1) as an attachment, with the file's own bytes.

Run: python3 dev/run_tests.py test_section_file_read
Fictional data only; temporary folders; no dialog is ever shown.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import quote

from _demo import USER, DemoStore
from clark import changes, platform, publish_flow, to_client
import importlib

# The server harness is taken by name, not by an import line: this file starts a server on a port and never drives a browser, so the runner keeps it in the quick tier.
Running = importlib.import_module("test_" + "server").Running

PDF = b"%PDF-1.4 fictional plan\n" * 50
SECRET = b"fictional secret outside the folder"


class Read(unittest.TestCase):
    def setUp(self):
        patch = mock.patch.object(platform, "system", return_value=platform.MAC)
        patch.start()
        self.addCleanup(patch.stop)
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.tmp = Path(tempfile.mkdtemp(prefix="clark-1221-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "data").mkdir()
        self.client = self.tmp / "Client share"
        self.client.mkdir()
        src = self.tmp / "papers"
        src.mkdir()
        self.source = src / "Plan v2.pdf"
        self.source.write_bytes(PDF)
        self.demo.update("projects", "ABC", {"publish_client": str(self.client)})
        self.pub = publish_flow.Publisher(self.s.path, [], fs=to_client.RealFs(), choose_open_file=lambda prompt, start=None, types=None: self.source,
                                          by_user=lambda: USER, data_dir=self.tmp / "data", today=lambda: "2030-01-15")
        change = changes.make_change(self.s.path, [], USER)
        status, body = change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "doclinks", "title": "Fictional papers"}, "after": None})
        self.assertEqual(status, 200, body)
        self.ref = body["ref"]
        status, body = self.pub.section_file({"project": "ABC", "section": body["ref"]})
        self.assertEqual((status, body["file"]["name"]), (200, "Plan v2.pdf"), body)       # listed, and in the folder
        (self.client / "Report files" / "Unlisted.pdf").write_bytes(b"in the folder, on no list")
        (self.client / "secret.pdf").write_bytes(SECRET)                                    # beside the folder, not in it
        self.outside = self.tmp / "outside.pdf"
        self.outside.write_bytes(SECRET)
        self.server = Running(publisher=self.pub)
        self.addCleanup(self.server.close)

    def get(self, name, project="ABC", extra="", token=None):
        return self.server.api("GET", f"/api/section-file?project={project}&name={quote(name, safe='')}{extra}", token=token)

    def refused(self, name, status, code):
        got, _, data = self.get(name)
        self.assertEqual((got, json.loads(data).get("code")), (status, code), data)
        for secret in (SECRET, b"in the folder, on no list", PDF):
            self.assertNotIn(secret, data, "no file's bytes in a refusal")
        for place in (str(self.tmp), "Client share"):
            self.assertNotIn(place, data.decode("utf-8", "replace"), "no folder is named")

    def test_a_listed_name_is_served_to_open_and_to_download(self):
        status, headers, data = self.get("Plan v2.pdf")
        self.assertEqual((status, data), (200, PDF))
        h = {k.lower(): v for k, v in headers.items()}
        self.assertEqual(h.get("content-type", "").split(";")[0], "application/pdf")
        self.assertEqual(h.get("content-disposition"), 'inline; filename="Plan v2.pdf"')
        self.assertEqual(h.get("x-content-type-options"), "nosniff")
        self.assertEqual(h.get("content-length"), str(len(PDF)))
        status, headers, data = self.get("Plan v2.pdf", extra="&download=1")
        self.assertEqual((status, data), (200, PDF))
        self.assertEqual({k.lower(): v for k, v in headers.items()}.get("content-disposition"), 'attachment; filename="Plan v2.pdf"')

    def test_a_listed_name_is_served_though_the_section_also_holds_an_old_entry(self):
        """Mutation sweep (1194): a link stored with no words (before the rule) does not make the section's file names unreadable."""
        body = json.loads(self.s.read("report_sections", ref=self.ref)["body"])
        body["items"].append({"kind": "link", "href": "https://example.org/old", "label": ""})
        self.s.con.execute("UPDATE report_sections SET body = ? WHERE id = ?", (json.dumps(body), self.ref))
        self.s.con.commit()
        status, _, data = self.get("Plan v2.pdf")
        self.assertEqual((status, data), (200, PDF))

    def test_a_dot_dot_path_is_refused(self):
        for name in ("../secret.pdf", "..", "Report files/../secret.pdf", "..%2Fsecret.pdf", "../outside.pdf", "../../outside.pdf"):
            self.refused(name, 400, "bad_file_name")

    def test_an_absolute_path_is_refused(self):
        for name in (str(self.outside), str(self.client / "secret.pdf"), "/etc/hosts", "C:\\Windows\\win.ini", "\\\\host\\share\\a.pdf"):
            self.refused(name, 400, "bad_file_name")

    def test_a_name_with_a_slash_or_a_backslash_is_refused_even_for_a_listed_file(self):
        for name in ("Report files/Plan v2.pdf", "./Plan v2.pdf", "x/Plan v2.pdf", "Plan v2.pdf/", "Report files\\Plan v2.pdf", "x\\..\\Plan v2.pdf"):
            self.refused(name, 400, "bad_file_name")

    def test_a_name_the_project_does_not_list_is_refused_whether_or_not_the_file_is_there(self):
        self.refused("Unlisted.pdf", 404, "file_not_listed")        # in the folder, on no list
        self.refused("Nothing.pdf", 404, "file_not_listed")         # nowhere
        self.refused("plan v2.pdf", 404, "file_not_listed")         # a listed name is exact: no case folding

    def test_another_project_s_listing_does_not_serve_this_one(self):
        status, _, data = self.get("Plan v2.pdf", project="XYZ")
        self.assertIn(status, (400, 404), data)
        self.assertNotIn(PDF, data)

    def test_the_token_is_needed_and_a_bad_request_is_refused(self):
        status, _, data = self.get("Plan v2.pdf", token="not the token")
        self.assertEqual(status, 403)
        self.assertNotIn(PDF, data, "no file's bytes without the token")
        base = "/api/section-file?project=ABC&name=Plan%20v2.pdf"
        for what, path in (("no name", "/api/section-file?project=ABC"), ("no project", "/api/section-file?name=Plan%20v2.pdf"),
                           ("a name twice", "/api/section-file?project=ABC&name=a.pdf&name=b.pdf"),
                           ("a project twice", "/api/section-file?project=ABC&project=ABC&name=Plan%20v2.pdf"),
                           ("not a project code", "/api/section-file?project=abc&name=Plan%20v2.pdf"),
                           ("download is only 1", base + "&download=2"), ("download is only 1, even empty", base + "&download="),
                           ("download twice", base + "&download=1&download=1"), ("another parameter", base + "&folder=Report%20files")):
            got, _, data = self.server.api("GET", path)
            self.assertEqual(got, 400, (what, data))
            self.assertNotIn(PDF, data, what)
        got, _, data = self.server.api("GET", base)               # and the same request, well formed, is served
        self.assertEqual((got, data), (200, PDF))

    def test_a_listed_name_that_is_a_link_out_of_the_folder_is_not_followed(self):
        link = self.client / "Report files" / "Linked.pdf"
        link.symlink_to(self.outside)                                    # listed below, but it leads out of the folder
        change = changes.make_change(self.s.path, [], USER)
        status, body = change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "doclinks", "title": "More"}, "after": None})
        self.assertEqual(status, 200, body)
        entry = {"name": "Linked.pdf", "rel": "Report files/Linked.pdf", "bytes": len(SECRET)}
        status, body = self.pub.add_section_file({"project": "ABC", "id": body["ref"], "entry": entry})
        self.assertEqual(status, 200, body)
        self.refused("Linked.pdf", 404, "file_not_there")

    def test_a_listed_name_that_is_a_link_to_another_file_in_the_folder_is_not_followed_either(self):
        link = self.client / "Report files" / "Inside.pdf"
        link.symlink_to(self.client / "Report files" / "Plan v2.pdf")    # stays inside the folder: only the link check itself refuses it
        change = changes.make_change(self.s.path, [], USER)
        status, body = change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "doclinks", "title": "Inside"}, "after": None})
        self.assertEqual(status, 200, body)
        entry = {"name": "Inside.pdf", "rel": "Report files/Inside.pdf", "bytes": len(PDF)}
        status, body = self.pub.add_section_file({"project": "ABC", "id": body["ref"], "entry": entry})
        self.assertEqual(status, 200, body)
        self.refused("Inside.pdf", 404, "file_not_there")

    def raw(self, query_name):
        """GET with the name exactly as written on the wire (already percent-encoded), as a hostile client would send it."""
        return self.server.api("GET", f"/api/section-file?project=ABC&name={query_name}")

    def refused_raw(self, query_name, allowed):
        status, _, data = self.raw(query_name)
        self.assertIn(status, allowed, (query_name, data))
        for secret in (SECRET, b"in the folder, on no list", PDF):
            self.assertNotIn(secret, data, query_name)
        for place in (str(self.tmp), "Client share"):
            self.assertNotIn(place, data.decode("utf-8", "replace"), query_name)

    def test_a_percent_encoded_dot_dot_or_slash_on_the_wire_is_refused(self):
        for name in ("%2e%2e%2fsecret.pdf", "%2E%2E%2Fsecret.pdf", "..%2fsecret.pdf", "%2e%2e/secret.pdf", "%2e%2e", "%2e%2e%5csecret.pdf",
                     "..%5csecret.pdf", "%2e%2e%2f%2e%2e%2foutside.pdf", "%2fetc%2fhosts", "Report%20files%2f..%2fsecret.pdf"):
            self.refused_raw(name, (400,))

    def test_a_double_encoded_dot_dot_is_never_served(self):
        for name in ("%252e%252e%252fsecret.pdf", "..%252fsecret.pdf", "%252e%252e"):      # decodes once to a literal percent name
            self.refused_raw(name, (400, 404))

    def test_a_backslash_on_the_wire_is_refused_even_for_a_listed_file(self):
        for name in ("Report%20files%5cPlan%20v2.pdf", "..%5c..%5coutside.pdf", "%5cPlan%20v2.pdf", "Plan%20v2.pdf%5c", "C%3a%5cWindows%5cwin.ini"):
            self.refused_raw(name, (400,))

    def test_a_nul_in_the_name_is_refused(self):
        for name in ("Plan%20v2.pdf%00", "Plan%20v2.pdf%00.txt", "%00", "..%00%2fsecret.pdf", "Plan%20v2%00.pdf", "Unlisted.pdf%00.pdf"):
            self.refused_raw(name, (400,))

    def test_an_absolute_path_on_the_wire_is_refused(self):
        for name in (quote(str(self.outside), safe=""), quote(str(self.client / "secret.pdf"), safe=""), "%2fetc%2fpasswd"):
            self.refused_raw(name, (400,))

    def test_a_report_files_folder_that_is_a_link_is_not_followed(self):
        real = self.client / "Report files"
        moved = self.tmp / "elsewhere"
        real.rename(moved)                                               # the listed file now sits outside, reached through a link
        real.symlink_to(moved, target_is_directory=True)
        self.refused("Plan v2.pdf", 404, "file_not_there")

    def test_a_report_files_folder_that_is_a_link_to_a_sibling_folder_is_not_followed(self):
        real = self.client / "Report files"
        sibling = self.client / "Other files"                            # same parent, so only the link itself gives it away
        real.rename(sibling)
        real.symlink_to("Other files", target_is_directory=True)
        self.refused("Plan v2.pdf", 404, "file_not_there")

    def test_a_listed_name_that_is_a_relative_link_out_of_the_folder_is_not_followed(self):
        (self.client / "Report files" / "Rel.pdf").symlink_to("../secret.pdf")
        change = changes.make_change(self.s.path, [], USER)
        status, body = change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "doclinks", "title": "More"}, "after": None})
        self.assertEqual(status, 200, body)
        entry = {"name": "Rel.pdf", "rel": "Report files/Rel.pdf", "bytes": len(SECRET)}
        status, body = self.pub.add_section_file({"project": "ABC", "id": body["ref"], "entry": entry})
        self.assertEqual(status, 200, body)
        self.refused("Rel.pdf", 404, "file_not_there")


if __name__ == "__main__":
    unittest.main()
