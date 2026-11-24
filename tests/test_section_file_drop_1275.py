"""Row 1275: a file dropped on the Documents and links section (server side), POST /api/section-file-drop.

The bytes come in the body, the project, the section and the URL-encoded name in headers. The rules are the file window's
(section_files.py): the client folder's "Report files" folder, one entry, one Undo (the file stays), a taken name numbered and never
overwritten, 25 MB for both, the row 1194 ending list and the first bytes judged before anything is written. The route checks the
token and the size before it reads the body, and the log names no file.

Run: python3 dev/run_tests.py test_section_file_drop_1275
Fictional data only; temporary folders; no dialog is ever shown.
"""
import json
import unittest
from unittest import mock
from urllib.parse import quote

import test_section_file_route as base
from _real_server import real_server
from clark import log as clark_log, page, section_files, server as sv, theme
from test_report_editor import EMPTY_BRANDING
from test_server import Running, chrome

PDF = base.PDF
OLE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"fictional legacy file"
PNG = b"\x89PNG\r\n\x1a\n" + b"fictional picture"
WIDTHS = (1400, 900)
SENTENCE = "That type of file can't be added. Use PDF, Word, Excel, PowerPoint, JPG, PNG or TXT."


class Drop(base.Route):
    def setUp(self):
        super().setUp()
        self.ref = self.section()

    def drop(self, name, data, ref=None, project="ABC"):
        return self.pub.drop_section_file(project, ref or self.ref, quote(name, safe=""), data)

    def over_http(self, name, data, ref=None, token=None, length=None, extra=None):
        server = Running(publisher=self.pub)
        self.addCleanup(server.close)
        headers = {"X-Clark-Project": "ABC", "X-Clark-Section": ref or self.ref, "X-Clark-File-Name": quote(name, safe=""), **(extra or {})}
        return server.api("POST", "/api/section-file-drop", data, ctype="application/octet-stream", token=token, extra=headers)

    def refused_drop(self, name, data, code, status=409):
        before, files = self.snapshot(), self.files()
        got = self.drop(name, data)
        self.assertEqual((got[0], got[1]["ok"], got[1]["code"]), (status, False, code), got)
        self.assertEqual(self.snapshot(), before, "nothing was written to the store")
        self.assertEqual(self.files(), files, "nothing was written to the client folder")
        return got[1]["message"]

    def test_a_dropped_file_is_added_like_the_file_window(self):
        status, window = self.attach(self.ref)
        self.assertEqual(status, 200, window)
        self.assertEqual(self.files(), ["Plan v2.pdf"])
        status, dropped = self.drop("Budget.pdf", PDF)
        self.assertEqual(status, 200, dropped)
        self.assertEqual(self.files(), ["Budget.pdf", "Plan v2.pdf"])
        self.assertEqual((self.client / "Report files" / "Budget.pdf").read_bytes(), PDF)
        entry = {"name": "Budget.pdf", "rel": "Report files/Budget.pdf", "bytes": len(PDF)}
        self.assertEqual(dropped["file"], entry)
        self.assertEqual(sorted(dropped), sorted(window), "the reply has the file window's shape")
        self.assertEqual(dropped["message"], section_files.ADDED.format(name="Budget.pdf"))
        self.assertEqual([i["name"] for i in self.items(self.ref)["items"]], ["Plan v2.pdf", "Budget.pdf"])
        applies = self.s.con.execute("SELECT count(DISTINCT apply_id) FROM change_log WHERE apply_id = ?", (dropped["apply_id"],)).fetchone()[0]
        self.assertEqual(applies, 1, "one step, so one Undo")
        status, undone = self.undo({"project": "ABC", "apply_id": dropped["apply_id"]})
        self.assertEqual(status, 200, undone)
        self.assertEqual([i["name"] for i in self.items(self.ref)["items"]], ["Plan v2.pdf"], "Undo takes the entry off")
        self.assertEqual(self.files(), ["Budget.pdf", "Plan v2.pdf"], "and leaves the file in Report files")

    def test_the_limit_is_25_mb_for_drop_and_file_window(self):
        self.assertEqual(section_files.MAX_FILE_BYTES, 25 * 1024 * 1024)
        self.assertEqual(sv.DROP_MAX_BYTES, section_files.MAX_FILE_BYTES)
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/section-file-drop"], 25 * 1024 * 1024)
        words = "That file is larger than 25 MB, so it was not added."
        self.assertEqual(section_files.MESSAGES["too_big"], words)
        self.assertEqual(sv.DROP_TOO_BIG, words)
        big = PDF + b"x" * (section_files.MAX_FILE_BYTES - len(PDF) + 1)
        self.assertEqual(self.refused_drop("Big.pdf", big, "too_big", 400), words)
        self.source.write_bytes(big)                          # the file window: the same limit, the same sentence
        self.assertEqual(self.refused(self.ref, "too_big"), words)
        edge = PDF + b"x" * (section_files.MAX_FILE_BYTES - len(PDF))      # exactly 25 MB is added
        status, body = self.drop("Edge.pdf", edge)
        self.assertEqual((status, body["file"]["bytes"]), (200, section_files.MAX_FILE_BYTES), body)

    def test_refused_types_get_the_1194_sentence_on_both_paths(self):
        for name in ("page.html", "pic.svg", "pack.zip", "tool.exe", "run.sh", "noending", "a.pdf.exe"):
            self.assertEqual(self.refused_drop(name, PDF, "bad_type"), f"{name}: {SENTENCE}", name)
            self.source = self.src / name
            self.source.write_bytes(PDF)
            self.chosen[0] = self.source
            self.assertEqual(self.refused(self.ref, "bad_type"), f"{name}: {SENTENCE}", name)
        got = self.drop(".pdf", PDF)      # a dropped name loses its leading dot first, so "pdf" has no ending
        self.assertEqual((got[0], got[1]["message"]), (409, f"pdf: {SENTENCE}"))
        for name, data in (("Upper.PDF", PDF), ("a.exe.pdf", PDF), ("Pic.PnG", PNG), ("Photo.JPG", b"\xff\xd8\xff\xe0fictional"), ("Sheet.XLSX", b"PK\x03\x04fictional")):
            status, body = self.drop(name, data)
            self.assertEqual((status, body["file"]["name"]), (200, name), body)

    def test_the_drop_and_the_file_window_read_the_one_list_of_row_1194(self):
        from clark.section_kinds import doclinks
        import inspect
        src = inspect.getsource(section_files)
        self.assertNotIn("ALLOWED_ENDINGS =", src, "section_files keeps no list of its own")
        self.assertNotIn("%PDF", src, "no first-bytes table is copied into section_files")
        for name, data in (("Sheet.csv", b"a,b\n1,2\n"), ("Pic.jpeg", b"\xff\xd8\xff\xe0fictional")):
            status, body = self.drop(name, data)
            self.assertEqual((status, body["file"]["name"]), (200, name), body)
        # one list object: change it and BOTH paths follow (a copy of the list in either path would still accept)
        shorter = tuple(e for e in doclinks.ALLOWED_ENDINGS if e not in ("csv", "jpeg"))
        with mock.patch.object(doclinks, "ALLOWED_ENDINGS", shorter):
            self.refused_drop("Other.csv", b"a,b\n", "bad_type")
            self.refused_drop("Other.jpeg", b"\xff\xd8\xff\xe0x", "bad_type")
            self.source = self.src / "Window.csv"
            self.source.write_bytes(b"a,b\n")
            self.chosen[0] = self.source
            self.assertEqual(self.refused(self.ref, "bad_type"), f"Window.csv: {SENTENCE}")
        self.assertIs(section_files.doclinks, doclinks)

    def test_first_bytes_check_txt_and_legacy_office(self):
        self.assertEqual(self.refused_drop("Notes.txt", b"plain\x00text", "bad_type"), f"Notes.txt: {SENTENCE}")
        self.refused_drop("Mid.txt", b"x" * 600 + b"\x00", "bad_type")                 # past the old 512, inside the first 8 KB
        self.refused_drop("Edge.txt", b"x" * 8191 + b"\x00", "bad_type")               # the last byte of the first 8 KB
        status, body = self.drop("Late.txt", b"x" * 8192 + b"\x00")
        self.assertEqual(status, 200, "a NUL after the first 8 KB is not judged")
        for name in ("Old.doc", "Old.xls", "Old.ppt"):
            status, body = self.drop(name, OLE)
            self.assertEqual((status, body["file"]["name"]), (200, name), body)
        self.refused_drop("Fake.pdf", b"not a pdf at all", "bad_type")
        self.refused_drop("Fake.docx", OLE, "bad_type")
        self.source = self.src / "Notes.txt"
        self.source.write_bytes(b"plain\x00text")
        self.chosen[0] = self.source
        self.assertEqual(self.refused(self.ref, "bad_type"), f"Notes.txt: {SENTENCE}", "the file window judges the same way")

    def test_a_dropped_name_clash_is_numbered(self):
        for n in range(1, 4):
            status, body = self.drop("Plan.pdf", PDF + str(n).encode())
            self.assertEqual((status, body["file"]["name"]), (200, "Plan.pdf" if n == 1 else f"Plan ({n}).pdf"), body)
        (self.client / "Report files" / "Plan (4).pdf").write_bytes(b"someone else's")
        status, body = self.drop("Plan.pdf", PDF + b"5")
        self.assertEqual(body["file"]["name"], "Plan (5).pdf")
        self.assertEqual((self.client / "Report files" / "Plan (4).pdf").read_bytes(), b"someone else's")
        self.assertEqual((self.client / "Report files" / "Plan.pdf").read_bytes(), PDF + b"1")
        for n in range(6, section_files.MAX_NUMBER + 1):
            (self.client / "Report files" / f"Plan ({n}).pdf").write_bytes(b"x")
        self.assertEqual(self.refused_drop("Plan.pdf", PDF, "names_taken"), section_files.MESSAGES["names_taken"])

    def test_dropped_name_is_cleaned_to_120_without_dot_or_path(self):
        for sent, kept in (("../../etc/Plan.pdf", "Plan.pdf"), ("C:\\Users\\x\\Sheet.pdf", "Sheet.pdf"), (".hidden.pdf", "hidden.pdf"),
                           ("...dots.pdf", "dots.pdf"), ("Tab\there\x01.pdf", "Tabhere.pdf"), ("a" * 200 + ".pdf", "a" * 116 + ".pdf")):
            status, body = self.drop(sent, PDF)
            self.assertEqual((status, body["file"]["name"]), (200, kept), (sent, body))
            self.assertLessEqual(len(body["file"]["name"]), 120)
        for sent in ("", "/", "..", "%FF%FE"):
            got = self.pub.drop_section_file("ABC", self.ref, sent, PDF)
            self.assertEqual((got[0], got[1]["code"]), (400, "drop_unread"), sent)
        self.assertEqual(sorted(p for p in self.files() if "/" in p or p.startswith(".")), [])

    def test_the_drop_route_checks_token_and_size_first(self):
        folder = self.tmp / "logs"
        handler = clark_log.install(clark_log.Log(folder))
        self.addCleanup(lambda: __import__("logging").getLogger("clark").removeHandler(handler))
        before, files = self.snapshot(), self.files()
        status, _, data = self.over_http("Secret plan.pdf", PDF, token="not the token")
        self.assertEqual(status, 403)
        self.assertEqual((self.snapshot(), self.files()), (before, files))
        server = Running(publisher=self.pub)
        self.addCleanup(server.close)
        head = {"X-Clark-Project": "ABC", "X-Clark-Section": self.ref, "X-Clark-File-Name": "Huge.pdf"}
        import http.client
        conn = http.client.HTTPConnection(sv.HOST, server.port, timeout=10)      # a length over the limit and no body sent: refused before a byte is read
        conn.putrequest("POST", "/api/section-file-drop", skip_accept_encoding=True)
        for k, v in {sv.TOKEN_HEADER: sv.TOKEN, "Content-Type": "application/octet-stream", "Content-Length": str(section_files.MAX_FILE_BYTES + 1), **head}.items():
            conn.putheader(k, v)
        conn.endheaders()
        r = conn.getresponse()
        body = json.loads(r.read())
        conn.close()
        self.assertEqual((r.status, body["code"], body["message"]), (400, "too_big", sv.DROP_TOO_BIG))
        status, _, data = server.api("POST", "/api/section-file-drop", PDF, ctype="application/json", extra=head)
        self.assertEqual(status, 415, "only raw bytes")
        status, _, data = self.over_http("Budget.pdf", PDF)
        self.assertEqual((status, json.loads(data)["file"]["name"]), (200, "Budget.pdf"), data)
        self.assertEqual(self.files(), ["Budget.pdf"])
        self.assertTrue(folder.is_dir(), "the log folder exists, so the log assert below reads something")
        logged = "".join(p.read_text(encoding="utf-8") for p in folder.glob("*.log"))
        self.assertTrue(logged, "the log has lines to check")
        for marker in ("Budget", "Secret plan", "Huge", "Client share", str(self.tmp)):
            self.assertNotIn(marker, logged)

    def test_a_drop_on_another_kind_of_section_adds_nothing(self):
        other = self.section("onedoc", "Fictional one")
        got = self.pub.drop_section_file("ABC", other, "Plan.pdf", PDF)
        self.assertEqual((got[0], got[1]["code"]), (400, "drop_wrong_section"))
        self.assertEqual(self.files(), None)


class InThePage(base.InThePage):
    """The drop area in Edit, through the real page and route: Classic only, the box and its over state, the words, one file at a
    time, and the file added like the file window's with one Undo. The box, the words and the refusal are checked at 1400 and 900 px."""

    def swap_page(self, with_theme):
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING, theme=theme.CLASSIC if with_theme else None),
                             seam=self.seam, publisher=self.pub)
        self.addCleanup(self.s.close)

    def classic(self):
        self.swap_page(True)

    def cards(self):
        self.swap_page(False)

    def open_edit(self, cdp, ref):
        p = self.visit(cdp)
        p.edit()
        p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] [data-add-file]')", "the Edit part drew")
        return p

    SEND = """(function (names, over) {
      const area = document.querySelector('[data-drop]');
      const dt = new DataTransfer();
      for (const n of names) dt.items.add(new File([%s], n, {type: ''}));
      area.dispatchEvent(new DragEvent(over ? 'dragenter' : 'drop', {dataTransfer: dt, bubbles: true, cancelable: true}));
    })"""

    def size(self, cdp, p, w):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"innerWidth === {w}", f"the window is {w} px wide")
        p.until("(function(){const r=document.querySelector('[data-drop]').getBoundingClientRect();return r.width>0&&r.right<=innerWidth&&r.left>=0&&document.documentElement.scrollWidth<=innerWidth;})()", f"the drop area fits the window at {w} px with no sideways scroll")

    def drag(self, p, names, over=False):
        p.js((self.SEND % json.dumps(PDF.decode("latin-1"))) + f"({json.dumps(names)}, {json.dumps(over)})")

    def test_a_dropped_file_is_added_like_the_file_window(self):
        self.classic()
        ref = self.add("doclinks")
        sel = f"[data-id={json.dumps(ref)}]"
        kept = []
        with chrome() as cdp:
            p = self.open_edit(cdp, ref)
            for w in WIDTHS:
                with self.subTest(width=w):
                    self.size(cdp, p, w)
                    name = f"Dropped plan {w}.pdf"
                    kept.append(name)
                    self.drag(p, [name])
                    p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 1", "the dropped file is drawn")
                    self.assertEqual(p.js(f"document.querySelector('{sel} .tpl-rename').value"), name)
                    p.until("!!document.querySelector('[data-undo]')", "one Undo toast")
                    self.assertEqual(p.js("document.querySelectorAll('[data-undo]').length"), 1)
                    self.assertEqual(sorted(x.name for x in (self.client / "Report files").iterdir()), sorted(kept))
                    self.assertEqual((self.client / "Report files" / name).read_bytes(), PDF)
                    p.js("document.querySelector('[data-undo]').click()")
                    p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 0", "Undo took the entry off")
                    self.assertEqual(sorted(x.name for x in (self.client / "Report files").iterdir()), sorted(kept), "the file stays")

    def test_the_drop_area_box_and_over_state_at_both_widths(self):
        self.classic()
        ref = self.add("doclinks")
        with chrome() as cdp:
            p = self.open_edit(cdp, ref)
            probe = lambda prop, tok: p.js(f"(function(){{const e=document.createElement('i');e.style.{prop}='var({tok})';document.body.appendChild(e);const v=getComputedStyle(e).{prop};e.remove();return v;}})()")
            box = "(function(){const s=getComputedStyle(document.querySelector('[data-drop]'));return [s.borderTopWidth,s.borderTopStyle,s.borderTopLeftRadius,s.paddingTop,s.paddingLeft,s.textAlign,s.marginTop,s.borderTopColor,s.color,s.backgroundColor];})()"
            for w in WIDTHS:
                with self.subTest(width=w):
                    self.size(cdp, p, w)
                    p.js("document.querySelector('[data-drop]').dispatchEvent(new DragEvent('dragleave', {bubbles: true}))")
                    p.until("!document.querySelector('[data-drop]').classList.contains('over')", "the over state ends when the drag leaves")
                    rest = p.js(box)
                    self.assertEqual(rest[1:7], ["dashed", "12px", "14px", "14px", "center", "10px"])
                    rule = p.js("(function(){for(const sh of document.styleSheets){let rs;try{rs=sh.cssRules}catch(e){continue}for(const r of rs){if(r.selectorText===\".tpl-drop\")return r.style.getPropertyValue(\"border\")}}return null})()")
                    self.assertTrue(str(rule).startswith("1.5px dashed"), "the stylesheet says 1.5px (a screen at one pixel per pixel draws it as 1px)")
                    self.drag(p, ["a.pdf"], over=True)
                    p.until("document.querySelector('[data-drop]').classList.contains('over')", "the over state")
                    over = p.js(box)
                    self.assertEqual(over[7], probe("color", "--brand-blue"), "the border is the blue token")
                    self.assertEqual(over[8], probe("color", "--brand-blue"), "and so is the text")
                    self.assertEqual(over[9], probe("color", "--brand-blue-tint"), "the fill is the tint token")
                    self.assertNotEqual(rest[7], over[7])
                    for dark in ("dark", "light"):
                        p.js(f"document.documentElement.dataset.theme = {json.dumps(dark)}")
                        self.assertEqual(p.js(box)[7], probe("color", "--brand-blue"), dark)

    def test_the_area_words_at_both_widths(self):
        self.classic()
        ref = self.add("doclinks")
        with chrome() as cdp:
            p = self.open_edit(cdp, ref)
            for w in WIDTHS:
                with self.subTest(width=w):
                    self.size(cdp, p, w)
                    self.assertEqual(p.js("document.querySelector('[data-drop]').textContent"), "Drop files here to add them.")
                    self.assertEqual(p.js("document.querySelector('[data-drop-line]').textContent"), "Dropped files are kept in the client folder, in Report files.")
                    self.assertTrue(p.js("document.querySelector('[data-drop]').compareDocumentPosition(document.querySelector('[data-drop-line]')) & Node.DOCUMENT_POSITION_FOLLOWING"))
                    self.drag(p, ["a.pdf"], over=True)
                    p.until("document.querySelector('[data-drop]').classList.contains('over')", "the over state")
                    self.assertEqual(p.js("document.querySelector('[data-drop]').textContent"), "Drop files here to add them.")

    def test_good_files_and_a_refused_one_show_what_was_added_with_its_undo_and_the_refusal(self):
        """Row 1593 (a reader reproduced it in Chrome): a drop of good files plus one refused file adds the good ones, and the ONE toast says
        what was added with its Undo button AND names the refused file with its reason (before: only the problem toast, no Undo)."""
        self.classic()
        ref = self.add("doclinks")
        sel = f"[data-id={json.dumps(ref)}]"
        with chrome() as cdp:
            p = self.open_edit(cdp, ref)
            for w in WIDTHS:
                with self.subTest(width=w):
                    self.size(cdp, p, w)
                    p.js("document.querySelectorAll('.toast').forEach(t => t.remove())")
                    self.drag(p, [f"Good one {w}.pdf", f"Good two {w}.pdf", f"Refused {w}.exe"])
                    p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length >= 2", "the good files are drawn")
                    p.until("!!document.querySelector('.toast [data-undo], [data-undo]')", "the Undo button is on the toast")
                    text = p.js("document.querySelector('.toast').textContent")
                    self.assertIn("2 files added.", text)
                    self.assertIn(f"Refused {w}.exe:", text, "the refused file is named")
                    self.assertEqual(p.js("document.querySelectorAll('[data-undo]').length"), 1, "one Undo")
                    p.js("document.querySelector('[data-undo]').click()")
                    p.until(f"document.querySelectorAll('{sel} .tpl-dl-i').length === 0", "Undo took the whole batch off")

    def test_a_folder_in_the_drop_is_refused_whole(self):
        """Row 1593 (replaces the several-files-or-a-folder test): several files are added now, a folder still refuses the whole drop."""
        self.classic()
        ref = self.add("doclinks")
        sel = f"[data-id={json.dumps(ref)}]"
        sentence = "Folders can't be added. Drop files, not folders."
        with chrome() as cdp:
            p = self.open_edit(cdp, ref)
            for w in WIDTHS:
                with self.subTest(width=w):
                    self.size(cdp, p, w)
                    p.js("document.querySelectorAll('.toast').forEach(t => t.remove())")
                    folder = ("(function(){const area=document.querySelector('[data-drop]');const ev=new DragEvent('drop',{bubbles:true,cancelable:true});"
                              "Object.defineProperty(ev,'dataTransfer',{value:{types:['Files'],files:[new File([''],'one.pdf'),new File([''],'Folder')],items:[{webkitGetAsEntry:()=>({isDirectory:false})},{webkitGetAsEntry:()=>({isDirectory:true})}]}});area.dispatchEvent(ev);})()")
                    p.js(folder)
                    p.until(f"!!document.querySelector('.toast') && document.querySelector('.toast').textContent.includes({json.dumps(sentence)})", "the refusal for a folder")
                    self.assertEqual(p.js(f"document.querySelectorAll('{sel} .tpl-dl-i').length"), 0)
                    self.assertFalse((self.client / "Report files").exists(), "nothing was copied")

    def test_cards_has_no_drop_area(self):
        self.cards()
        ref = self.add("doclinks")
        with chrome() as cdp:
            p = self.open_edit(cdp, ref)
            self.assertFalse(p.js("!!document.getElementById('theme')"), "this page is Cards: no theme layer")
            self.assertFalse(p.js("!!document.querySelector('[data-drop], [data-drop-line], .tpl-drop')"))
        self.classic()
        with chrome() as cdp:
            p = self.open_edit(cdp, ref)
            self.assertTrue(p.js("!!document.querySelector('[data-drop]')"), "and Classic has it")


if __name__ == "__main__":
    unittest.main()
