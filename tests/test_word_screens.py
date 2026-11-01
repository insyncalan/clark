"""#48: the Word screens on the page, in a real browser against the real Word and publish routes: Export to Word (profile menu),
Also a Word document (Publish box), Import from Word (profile menu, Edit only). Fictional data only.

Run: python3 dev/run_tests.py -j 1 test_word_screens
Each browser test starts headless Chrome through the harness (tests/test_server.py chrome()) and the real server of
tests/test_publish_route.py's Rig (a real store with the #39 plant, the real publisher, the real change and undo routes) with the
real Word seams of word_route.py added; the system's folder window is replaced through the Word export's own seam. Widths 1400 and
900, light and dark (the browser's own colour scheme). Chrome is required: these fail, never skip, without it. The words tests and the
published-file tests need no browser.

What is asserted: an export saves a Word file and says where; a taken name asks first and writes nothing until answered; To client
copies only when ticked; a refusal is in the server's own words; busy is said in words; the import shows what it read BEFORE anything
is added, adds only the ticked items and only when Add is pressed, shows the toast with Undo, and one Undo removes the lot; a file that
is not a Word file and one over the size limit are refused in words (the big one before it is sent); View and the published file have
none of it.
"""
import base64
import json
import re
import sqlite3
import threading
import unittest
from pathlib import Path

from _paths import SRC
from test_docx_read import docx
from test_page import navigate
from test_publish_dialog import Pg, WIDTHS
from test_publish_route import DAY, USER, WANTED, Rig
from test_server import chrome, wait
from test_word_route import body as notes_body

from clark import page, word_route

PAGE_SRC = SRC / "clark" / "page" / "src"
SCHEMES = ("light", "dark")
NO_FOLDER = "No client folder yet. Set it in Settings."
NAME = "week notes.docx"
JARGON = r"(?i)\bzip\b|\bxml\b|\bentity\b|\bdtd\b|\brelationship|traceback|exception|errno|\bsql\b|\bjson\b|\bschema\b|fingerprint|base64|\bapi\b|\broute\b"
NEW_STRINGS = ("Export to Word", "Import from Word", "Also a Word document", "/api/word-export", "/api/word-import", "word-export-dialog",
               "word-import-dialog", "Read the file", "Tick all", "Untick all", "Add a number", "Replace it", "wordclash")


def encoded(data):
    return base64.b64encode(data).decode("ascii")


class Screens(unittest.TestCase):
    """A rig with the Word seams, a folder for Word reports, and a record of what the page sent to the Word routes."""
    saved = True

    def setUp(self):
        word_route.PLANS.clear()
        self.addCleanup(word_route.PLANS.clear)
        self.start()

    def start(self, saved=None):
        """A fresh rig (so a test can run its steps under each width and colour scheme from the start)."""
        self.rig = Rig(self, saved=self.saved if saved is None else saved)
        self.reports = self.rig.root / "Reports"
        self.reports.mkdir()
        self.sent, self.asked, self.gate = [], [], None
        self.pick = str(self.reports)
        roots = [str(self.rig.onedrive)]
        real_in = word_route.make_word_import(self.rig.db, roots, USER, today=lambda: DAY)
        real_out = word_route.make_word_export(self.rig.db, roots, USER, today=lambda: DAY, choose_folder=self.choose)

        def record(which, real):
            def call(req):
                self.sent.append((which, {k: (v if k != "data" else f"<{len(v)} characters>") for k, v in req.items()}))
                return real(req)
            return call
        self.rig.httpd.word_import = record("import", real_in)
        self.rig.httpd.word_export = record("export", real_out)

    def choose(self, prompt):
        self.asked.append(prompt)
        if self.gate:
            self.gate.wait(20)
        return self.pick

    # ---- the browser ----
    def page(self, cdp, width=1400, scheme="light", edit=False):
        sid = navigate(cdp, self.rig.httpd.server_port, "#dashboard&p=PUB")
        p = Pg(self, cdp, sid)
        p.until("!!document.querySelector('#profile-btn')", "the profile circle is in the top bar")
        p.width(width)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        if edit:
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("document.querySelector('[data-mode=edit]').getAttribute('aria-pressed') === 'true'", "Edit")
        return p

    def menu(self, p):
        p.js("document.querySelector('#profile-btn').click()")
        p.until("!!document.querySelector('#profile-menu')", "the menu opened")

    def labels(self, p):
        return p.js("[].map.call(document.querySelectorAll('#profile-menu [role=menuitem]'), function(e){return e.textContent})")

    def pick_entry(self, p, kind, box):
        self.menu(p)
        p.js("document.querySelector('#profile-menu [data-kind=%s]').click()" % kind)
        p.until("!!document.querySelector('#%s[open]')" % box, "the box opened")

    def open_export(self, p):
        self.pick_entry(p, "word-export", "word-export-dialog")

    def open_import(self, p):
        self.pick_entry(p, "word-import", "word-import-dialog")

    def text(self, p, box):
        return p.js("document.querySelector('#%s').innerText" % box)

    def msg(self, p):
        return p.js("(document.querySelector('#word-msg') || {}).innerText || ''")

    def focus_is(self, p):
        return p.js("(function(){var e=document.activeElement;return e.id || e.getAttribute('data-go') !== null && 'go' || e.tagName})()")

    def colours(self, p, box, scheme):
        """The box is drawn from the page's colour tokens: its background follows the scheme, and its words and its small grey words
        keep a contrast ratio of at least 4.5 to 1 against it."""
        got = p.js("""(function(){var d=document.querySelector('#%s'), bg=getComputedStyle(d).backgroundColor, out={bg:bg};
            var pick=function(sel){var e=d.querySelector(sel); return e?getComputedStyle(e).color:null};
            out.body=getComputedStyle(d).color; out.small=pick('.dlg-sub')||pick('small')||pick('.muted'); return out})()""" % box)

        def lum(rgb):
            r, g, b = [int(x) for x in re.findall(r"\d+", rgb)[:3]]
            f = lambda c: (c / 255 / 12.92) if c / 255 <= 0.03928 else (((c / 255) + 0.055) / 1.055) ** 2.4
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

        ratio = lambda a, b: (max(lum(a), lum(b)) + 0.05) / (min(lum(a), lum(b)) + 0.05)
        self.assertGreaterEqual(ratio(got["body"], got["bg"]), 4.5, f"{scheme}: the words on the box")
        if got["small"]:
            self.assertGreaterEqual(ratio(got["small"], got["bg"]), 4.5, f"{scheme}: the small grey words on the box")
        return lum(got["bg"])

    def inside(self, p, box):
        self.assertTrue(p.js("(function(){var r=document.querySelector('#%s').getBoundingClientRect();"
                             "return r.left>=0&&r.right<=innerWidth&&r.top>=0&&r.bottom<=innerHeight&&document.documentElement.scrollWidth<=innerWidth})()" % box),
                        "the box is inside the window, and the page has no sideways scroll")

    def database(self, sql, *args):
        con = sqlite3.connect(str(self.rig.db))
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args).fetchall()]
        finally:
            con.close()

    def counts(self):
        return {t: self.database(f"SELECT count(*) AS n FROM {t} WHERE project = 'PUB'")[0]["n"] for t in ("actions", "raid", "decisions")}

    def word_files(self, folder):
        return sorted(p.name for p in Path(folder).iterdir() if p.suffix == ".docx")

    def toast(self, p):
        p.until("!!document.querySelector('.toast .toast-text')", "a message appeared")
        return p.js("(function(){var t=document.querySelector('.toast');return {text:t.querySelector('.toast-text').textContent,kind:t.dataset.kind,undo:!!t.querySelector('[data-undo]')}})()")

    def choose_file(self, p, data, name=NAME):
        """Put a file in the picker as a person would (the browser's own file object), then let the page see the change."""
        p.js("""(function(b64, name){var bin=atob(b64), u=new Uint8Array(bin.length); for(var i=0;i<bin.length;i++)u[i]=bin.charCodeAt(i);
            var dt=new DataTransfer(); dt.items.add(new File([u], name, {type:'application/octet-stream'}));
            var el=document.querySelector('#word-file'); el.files=dt.files; el.dispatchEvent(new Event('change',{bubbles:true}))})(%s, %s)"""
             % (json.dumps(encoded(data)), json.dumps(name)))

    def read_it(self, p, data=None, name=NAME):
        self.choose_file(p, docx(notes_body()) if data is None else data, name)
        p.until("!document.querySelector('[data-read]').disabled", "a chosen file lets Read the file be pressed")
        p.js("document.querySelector('[data-read]').click()")


# ── Export to Word ───────────────────────────────────────────────────────────────

class Export(Screens):
    def test_the_menu_has_the_entry_in_view_and_edit_and_the_tooltip_is_unchanged(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.menu(p)
            view = self.labels(p)
            self.assertIn("Export to Word", view)
            self.assertEqual(view.index("Export to Word"), view.index("Export to Excel") + 1)
            self.assertNotIn("Import from Word", view, "View adds nothing, so it has no import")
            self.assertEqual(p.js("document.querySelector('#profile-btn').title"), "Your menu: Publish, Preview, Export, Settings")

    def test_an_export_saves_a_file_and_says_where(self):
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    self.start()
                    p = self.page(cdp, w, scheme)
                    self.open_export(p)
                    self.inside(p, "word-export-dialog")
                    text = self.text(p, "word-export-dialog")
                    self.assertIn("Export to Word", text)
                    self.assertIn("Save the Word report", text)
                    self.assertIn("Also copied to the client folder: Harbour Bridge", text)
                    self.assertEqual(p.js("[document.querySelector('#word-client').checked, document.querySelector('#word-client').disabled]"),
                                     [False, False], "To client is unticked every time")
                    self.assertNotIn("The client will see", text)
                    self.colours(p, "word-export-dialog", scheme)
                    self.assertEqual((self.word_files(self.reports), self.rig.rows()), ([], []), "opening writes nothing")
                    p.js("document.querySelector('[data-go]').click()")
                    p.until("document.querySelector('[data-go]').innerText === 'Close'", "it was saved")
                    name = f"PUB-report-{WANTED[len('PUB-report-'):-len('.html')]}.docx"
                    self.assertEqual(self.msg(p), f"Saved “{name}” in “Reports”.", "it says what and where")
                    self.assertEqual(self.word_files(self.reports), [name])
                    data = (self.reports / name).read_bytes()
                    self.assertTrue(data.startswith(b"PK"))
                    (row,) = self.rig.rows()
                    self.assertEqual((row["word"], row["local_path"], row["client_path"], row["by_user"]), (1, str(self.reports / name), None, USER))
                    self.assertEqual(self.rig.listing(self.rig.client), [], "nothing went to the client")
                    self.assertEqual(self.focus_is(p), "go", "focus is on Close")
                    p.js("document.querySelector('[data-go]').click()")
                    p.until("!document.querySelector('#word-export-dialog')", "it closed")
                    self.assertEqual(self.focus_is(p), "profile-btn", "focus goes back to the profile circle")
                    self.assertEqual(self.sent, [("export", {"project": "PUB", "to_client": False})])

    def test_to_client_copies_only_when_it_is_ticked(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp)
            self.open_export(p)
            p.js("document.querySelector('#word-client').click()")
            p.until("document.querySelector('[data-go]').innerText === 'Save and send to the client'", "the button says so")
            self.assertIn("The client will see this report.", self.text(p, "word-export-dialog"))
            p.js("document.querySelector('[data-go]').click()")
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "it was saved")
            name = self.word_files(self.reports)[0]
            self.assertEqual(self.rig.listing(self.rig.client), [name], "the copy is in the client folder")
            self.assertEqual((self.rig.client / name).read_bytes(), (self.reports / name).read_bytes())
            self.assertIn("also copied to the client folder", self.msg(p))
            self.assertEqual(self.sent[-1], ("export", {"project": "PUB", "to_client": True}))
            p.js("document.querySelector('[data-go]').click()")
            p.until("!document.querySelector('#word-export-dialog')", "closed")
            self.open_export(p)
            self.assertFalse(p.js("document.querySelector('#word-client').checked"), "reopened: unticked, never remembered")

    def test_with_no_client_folder_to_client_is_off_and_says_so(self):
        with chrome() as cdp:
            self.start(saved=False)
            p = self.page(cdp)
            self.open_export(p)
            self.assertTrue(p.js("document.querySelector('#word-client').disabled"))
            self.assertIn(NO_FOLDER, self.text(p, "word-export-dialog"))
            self.assertEqual(p.js("document.activeElement.hasAttribute('data-go')"), True, "focus starts on the button")

    def test_a_taken_name_asks_first_and_writes_nothing_until_answered(self):
        for w, scheme in ((1400, "light"), (900, "dark")):
            with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                self.start()
                p = self.page(cdp, w, scheme)
                self.open_export(p)
                p.js("document.querySelector('[data-go]').click()")
                p.until("document.querySelector('[data-go]').innerText === 'Close'", "the first export was saved")
                first = self.word_files(self.reports)[0]
                p.js("document.querySelector('[data-go]').click()")
                p.until("!document.querySelector('#word-export-dialog')", "closed")
                before = (self.word_files(self.reports), len(self.rig.rows()))
                self.open_export(p)
                p.js("document.querySelector('[data-go]').click()")
                p.until("!!document.querySelector('input[name=word-clash]')", "the question was asked")
                text = self.text(p, "word-export-dialog")
                self.assertIn(f"A file called “{first}” is already in “Reports”. Nothing was saved yet.", text)
                self.assertIn("Add a number", text)
                self.assertIn("Replace it", text)
                self.inside(p, "word-export-dialog")
                self.colours(p, "word-export-dialog", scheme)
                self.assertEqual(p.js("document.querySelector('input[name=word-clash]:checked').value"), "number", "Add a number is the default")
                self.assertEqual((self.word_files(self.reports), len(self.rig.rows())), before, "nothing was written by asking")
                self.assertEqual(self.focus_is(p), "INPUT", "focus is on the chosen answer")
                # Replace needs its own confirmation
                p.js("document.querySelector('input[value=overwrite]').click()")
                p.until("!!document.querySelector('#word-confirm')", "the confirmation")
                self.assertTrue(p.js("document.querySelector('[data-go]').disabled"), "Replace cannot be pressed until it is confirmed")
                # Esc is Cancel: nothing written, focus back on the circle
                p.key("Escape", code="Escape", vk=27)
                p.until("!document.querySelector('#word-export-dialog')", "Esc cancels the question")
                self.assertEqual(self.focus_is(p), "profile-btn")
                self.assertEqual((self.word_files(self.reports), len(self.rig.rows())), before)
                # Add a number goes through
                self.open_export(p)
                p.js("document.querySelector('[data-go]').click()")
                p.until("!!document.querySelector('input[name=word-clash]')", "asked again")
                p.js("document.querySelector('[data-go]').click()")
                p.until("document.querySelector('[data-go]').innerText === 'Close'", "saved with a number")
                self.assertEqual(self.word_files(self.reports), sorted([first, first.replace(".docx", " (2).docx")]))
                self.assertIn("(2).docx", self.msg(p))
                self.assertEqual(self.sent[-1][1]["on_clash"], "number")
                p.js("document.querySelector('[data-go]').click()")
                p.until("!document.querySelector('#word-export-dialog')", "closed")
                # Replace, once confirmed, replaces the file and adds no second one
                old = (self.reports / first).read_bytes()
                (self.reports / first).write_bytes(b"an earlier file")
                self.open_export(p)
                p.js("document.querySelector('[data-go]').click()")
                p.until("!!document.querySelector('input[name=word-clash]')", "asked a third time")
                p.js("document.querySelector('input[value=overwrite]').click()")
                p.until("!!document.querySelector('#word-confirm')", "the confirmation")
                p.js("document.querySelector('#word-confirm').click()")
                p.until("!document.querySelector('[data-go]').disabled", "confirmed")
                p.js("document.querySelector('[data-go]').click()")
                p.until("document.querySelector('[data-go]').innerText === 'Close'", "replaced")
                self.assertEqual((self.reports / first).read_bytes(), old, "the old file was replaced by the report")
                self.assertEqual(len(self.word_files(self.reports)), 2)
                self.assertEqual(self.sent[-1][1], {"project": "PUB", "to_client": False, "on_clash": "overwrite", "confirmed": True})

    def test_a_refusal_is_shown_in_the_servers_own_words_and_writes_nothing(self):
        for w, scheme in ((1400, "dark"), (900, "light")):
            with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                self.start()
                self.pick = str(self.rig.data_dir)                      # clark's own data folder is no place for a report
                p = self.page(cdp, w, scheme)
                self.open_export(p)
                p.js("document.querySelector('[data-go]').click()")
                p.until("/inside clark.s own data folder/.test(document.querySelector('#word-msg').innerText)", "the refusal was said")
                self.assertEqual(self.msg(p), "That folder is inside clark's own data folder. Choose a folder for reports.")
                self.assertEqual(p.js("document.querySelector('#word-msg').getAttribute('role')"), "alert")
                self.assertNotRegex(self.msg(p), JARGON)
                self.assertEqual((self.word_files(self.rig.data_dir), self.word_files(self.reports), self.rig.rows()), ([], [], []))
                self.assertFalse(p.js("document.querySelector('[data-go]').disabled"), "the box is still usable")
                self.assertEqual(p.js("document.querySelector('#word-msg .error') !== null"), True)

    def test_busy_is_said_in_words_and_the_buttons_are_off(self):
        with chrome() as cdp:
            self.start()
            self.gate = threading.Event()
            self.addCleanup(self.gate.set)
            p = self.page(cdp)
            self.open_export(p)
            p.js("document.querySelector('[data-go]').click()")
            p.until("/Saving the Word report/.test(document.querySelector('#word-msg').innerText)", "it says it is saving")
            self.assertIn("If a window asks where to save it, choose a folder there.", self.msg(p))
            self.assertEqual(p.js("document.querySelector('#word-export-dialog').getAttribute('aria-busy')"), "true")
            self.assertTrue(p.js("document.querySelector('[data-go]').disabled && document.querySelector('[data-cancel]').disabled && document.querySelector('#word-client').disabled"))
            p.key("Escape", code="Escape", vk=27)
            self.assertTrue(p.js("!!document.querySelector('#word-export-dialog')"), "Esc does not close it while it is saving")
            self.gate.set()
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "it finished")
            self.assertEqual(p.js("document.querySelector('#word-export-dialog').getAttribute('aria-busy')"), "false")
            self.assertEqual(self.asked, ["Choose the folder for the Word report"], "the folder window was asked for once")

    def test_the_keyboard(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp)
            self.menu(p)
            p.js("document.querySelector('#profile-menu [data-kind=word-export]').focus()")
            p.key("Enter", code="Enter", vk=13)
            p.until("!!document.querySelector('#word-export-dialog[open]')", "Enter on the entry opened the box")
            p.until("document.activeElement && document.activeElement.id === 'word-client'", "focus starts on the To client tick")
            p.key(" ", code="Space", vk=32)
            p.until("document.querySelector('#word-client').checked", "Space ticks it")
            p.key("Tab", code="Tab", vk=9)
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-cancel')"), "Tab goes to Cancel, then to the button")
            p.key("Tab", code="Tab", vk=9)
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-go')"))
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#word-export-dialog')", "Esc cancels")
            self.assertEqual(self.focus_is(p), "profile-btn", "focus returns to the circle")
            self.assertEqual((self.word_files(self.reports), self.rig.rows(), self.sent), ([], [], []), "Esc exported nothing")


# ── Also a Word document, in the Publish box ─────────────────────────────────────────────────

class WordToo(Screens):
    def publish_with(self, p, client=False, word=True):
        p.open_publish()
        if client:
            p.js("document.querySelector('#pub-client').click()")
        if word:
            p.js("document.querySelector('#pub-word').click()")
        p.go()

    def test_the_tick_is_in_the_box_and_is_unticked_every_time(self):
        for w, scheme in ((1400, "light"), (900, "dark")):
            with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                self.start()
                p = self.page(cdp, w, scheme)
                p.open_publish()
                text = p.dialog_text()
                self.assertIn("Also a Word document", text)
                self.assertIn("A Word copy of the report, saved beside the web page.", text)
                self.assertEqual(p.js("[document.querySelector('#pub-word').checked, document.querySelector('#pub-word').disabled]"), [False, False])
                self.inside(p, "publish-dialog")
                self.colours(p, "publish-dialog", scheme)
                p.js("document.querySelector('#pub-word').click()")
                p.js("document.querySelector('#pub-client').click()")
                self.assertIn("The client will see this page and the Word report.", p.dialog_text())
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('#publish-dialog')", "closed")
                p.open_publish()
                self.assertFalse(p.js("document.querySelector('#pub-word').checked"), "reopened: unticked, never remembered")
                self.assertEqual(p.js("localStorage.length + sessionStorage.length"), 0)

    def test_ticked_it_saves_the_word_report_beside_the_web_page_and_says_both(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp)
            self.publish_with(p)
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "both were saved")
            said = p.message()
            self.assertIn("PUB-report-2026-10-23", said)
            self.assertRegex(said, r"Saved “PUB-report-2026-10-23\.docx” in “Local”\.")
            self.assertEqual(self.word_files(self.rig.local), ["PUB-report-2026-10-23.docx"], "beside the web page")
            self.assertTrue((self.rig.local / "chosen.html").exists())
            self.assertEqual(sorted(r["word"] for r in self.rig.rows()), [0, 1], "one row for the web page, one for the Word file")
            self.assertEqual(self.sent, [("export", {"project": "PUB", "to_client": False})], "the Word report goes by the one Word route")
            self.assertEqual(self.rig.listing(self.rig.client), [])

    def test_with_to_client_the_word_copy_goes_to_the_client_folder_too(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp)
            self.publish_with(p, client=True)
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "both were saved")
            self.assertEqual(self.rig.listing(self.rig.client), sorted([WANTED, "PUB-report-2026-10-23.docx"]))
            self.assertEqual(self.sent, [("export", {"project": "PUB", "to_client": True})])

    def test_unticked_it_makes_no_word_file_and_asks_the_word_route_nothing(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp)
            self.publish_with(p, word=False)
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
            self.assertEqual(self.word_files(self.rig.local), [])
            self.assertEqual((self.sent, [r["word"] for r in self.rig.rows()]), ([], [0]))

    def test_busy_says_which_step_it_is_on(self):
        with chrome() as cdp:
            self.start()
            self.gate = threading.Event()
            self.addCleanup(self.gate.set)
            p = self.page(cdp)
            # the folder window only opens when there is no folder; publishing first records one, so hold the Word route itself
            held = self.rig.httpd.word_export

            def slow(req):
                self.gate.wait(20)
                return held(req)
            self.rig.httpd.word_export = slow
            self.publish_with(p)
            p.until("/Saving the Word report/.test(document.querySelector('#pub-msg').innerText)", "it says it is on the Word step")
            self.assertTrue(p.js("document.querySelector('[data-go]').disabled && document.querySelector('#pub-word').disabled"))
            self.assertTrue((self.rig.local / "chosen.html").exists(), "the web page was already published")
            self.gate.set()
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "both done")

    def test_a_taken_word_name_asks_and_cancel_leaves_the_published_page_published(self):
        with chrome() as cdp:
            self.start()
            (self.rig.local / "PUB-report-2026-10-23.docx").write_bytes(b"an earlier file")
            p = self.page(cdp)
            self.publish_with(p)
            p.until("!!document.querySelector('input[name=word-clash]')", "the question about the Word file was asked")
            self.assertIn("The Word file name is taken", p.dialog_text())
            self.assertIn("Add a number", p.dialog_text())
            self.assertTrue((self.rig.local / "chosen.html").exists(), "the web page is published already")
            self.assertEqual((self.rig.local / "PUB-report-2026-10-23.docx").read_bytes(), b"an earlier file", "the Word file is untouched")
            p.js("document.querySelector('[data-cancel]').click()")
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "it ended in the box, not closed")
            self.assertIn("The Word report was not saved.", p.message())
            self.assertIn("Published", p.message() + p.dialog_text())
            p.js("document.querySelector('[data-go]').click()")
            p.until("!document.querySelector('#publish-dialog')", "closed")
            self.assertEqual(self.focus_is(p), "profile-btn")

    def test_a_taken_word_name_is_answered_with_a_number(self):
        with chrome() as cdp:
            self.start()
            (self.rig.local / "PUB-report-2026-10-23.docx").write_bytes(b"an earlier file")
            p = self.page(cdp)
            self.publish_with(p)
            p.until("!!document.querySelector('input[name=word-clash]')", "asked")
            p.go()
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "saved with a number")
            self.assertEqual(self.word_files(self.rig.local), ["PUB-report-2026-10-23 (2).docx", "PUB-report-2026-10-23.docx"])
            self.assertEqual(self.sent[-1][1]["on_clash"], "number")


# ── Import from Word ─────────────────────────────────────────────────────────────

class Import(Screens):
    def test_the_entry_is_in_edit_only(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.menu(p)
            self.assertNotIn("Import from Word", self.labels(p))
            p.key("Escape", code="Escape", vk=27)
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("document.querySelector('[data-mode=edit]').getAttribute('aria-pressed') === 'true'", "Edit")
            self.menu(p)
            labels = self.labels(p)
            self.assertEqual(labels.index("Import from Word"), labels.index("Export to Word") + 1)
            self.assertEqual(p.js("document.querySelector('#profile-btn').title"), "Your menu: Publish, Preview, Export, Settings")

    def test_it_shows_what_it_read_before_anything_is_added_then_adds_only_what_is_chosen_with_one_undo(self):
        for w in WIDTHS:
            for scheme in SCHEMES:
                with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                    self.start()
                    p = self.page(cdp, w, scheme, edit=True)
                    before = self.counts()
                    self.open_import(p)
                    self.inside(p, "word-import-dialog")
                    self.assertEqual(self.focus_is(p), "word-file", "focus starts on the file picker")
                    self.assertIn("Choose a Word file (.docx) of up to 25 MB.", self.text(p, "word-import-dialog"))
                    self.assertTrue(p.js("document.querySelector('[data-read]').disabled"), "Read the file waits for a file")
                    self.colours(p, "word-import-dialog", scheme)
                    self.read_it(p)
                    # the preview: what was read, with nothing added
                    p.until("!!document.querySelector('#word-import-dialog [data-add]')", "the preview is shown")
                    text = self.text(p, "word-import-dialog")
                    self.assertIn("4 new items found in week notes.docx. Nothing is added until you choose.", text)
                    self.assertEqual(p.js("document.querySelectorAll('.wi-item input').length"), 4)
                    self.assertEqual(p.js("[].map.call(document.querySelectorAll('.wi-item'), function(e){return e.innerText.split('.')[0]})"), ["1", "2", "3", "4"])
                    self.assertIn("New action", text)
                    self.assertIn("Chase the supplier", text)
                    self.assertIn("Not shown to the client until you turn it on.", text)
                    self.assertEqual(p.js("document.querySelector('#word-import-dialog [data-add]').innerText"), "Add 4 items")
                    self.assertEqual(self.counts(), before, "reading adds nothing")
                    self.assertEqual([k for k, _ in self.sent], ["import"])
                    self.assertEqual(self.sent[0][1]["op"], "check")
                    self.inside(p, "word-import-dialog")
                    self.colours(p, "word-import-dialog", scheme)
                    self.assertTrue(p.js("document.activeElement.hasAttribute('data-add')"), "focus is on Add")
                    # choose: untick items 2 and 4 by their boxes
                    p.js("document.querySelector('.wi-item input[data-n=\"2\"]').click()")
                    p.js("document.querySelector('.wi-item input[data-n=\"4\"]').click()")
                    p.until("document.querySelector('#word-import-dialog [data-add]').innerText === 'Add 2 items'", "the button follows the ticks")
                    p.js("document.querySelector('[data-all=off]').click()")
                    p.until("document.querySelector('#word-import-dialog [data-add]').disabled && document.querySelector('#word-import-dialog [data-add]').innerText === 'Add items'", "nothing ticked: nothing to add")
                    p.js("document.querySelector('[data-all=on]').click()")
                    p.until("document.querySelector('#word-import-dialog [data-add]').innerText === 'Add 4 items'", "all ticked again")
                    p.js("document.querySelector('.wi-item input[data-n=\"2\"]').click()")
                    p.js("document.querySelector('.wi-item input[data-n=\"4\"]').click()")
                    p.until("document.querySelector('#word-import-dialog [data-add]').innerText === 'Add 2 items'", "two ticked")
                    self.assertEqual(self.counts(), before, "ticking adds nothing")
                    self.assertEqual([k for k, _ in self.sent], ["import"], "no second request before the choice")
                    p.js("document.querySelector('#word-import-dialog [data-add]').click()")
                    p.until("!document.querySelector('#word-import-dialog')", "it added the two and closed")
                    self.assertEqual(self.focus_is(p), "profile-btn")
                    self.assertEqual(self.sent[1], ("import", {"op": "apply", "project": "PUB", "plan": self.sent[1][1]["plan"], "accept": [1, 3]}))
                    after = self.counts()
                    self.assertEqual((after["actions"] - before["actions"], after["raid"] - before["raid"], after["decisions"] - before["decisions"]), (1, 1, 0))
                    new = self.database("SELECT client_visible, source FROM actions WHERE project = 'PUB' AND description = 'Draft the brief'")
                    self.assertEqual(new, [], "an item that was not ticked was not added")
                    chosen = self.database("SELECT client_visible, source FROM actions WHERE project = 'PUB' AND description = 'Chase the supplier'")
                    self.assertEqual([r["client_visible"] for r in chosen], [0], "hidden from the client until turned on")
                    steps = self.database("SELECT count(DISTINCT apply_id) AS n FROM change_log WHERE via = 'word'")
                    self.assertEqual(steps[0]["n"], 1, "one step")
                    # the toast, with Undo
                    t = self.toast(p)
                    self.assertEqual(t["kind"], "done")
                    self.assertTrue(t["undo"])
                    self.assertIn("Added 2 new item(s) from week notes.docx as one step you can undo.", t["text"])
                    self.assertIn("They are not shown to the client until you turn them on.", t["text"])
                    p.js("document.querySelector('.toast [data-undo]').click()")
                    p.until("/Put back/.test(document.querySelector('.toast .toast-text').textContent)", "the undo was said")
                    self.assertEqual(self.counts(), before, "one Undo takes the whole import back")
                    self.assertEqual(self.sent[-1], ("import", {"op": "undo", "project": "PUB", "apply_id": self.sent[-1][1]["apply_id"]}))
                    self.assertIn("2 item(s) from the Word import were removed.", p.js("document.querySelector('.toast .toast-text').textContent"))

    def test_accept_all_is_sent_as_all_and_the_work_items_show_the_new_ones(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp, edit=True)
            before = self.counts()
            self.open_import(p)
            self.read_it(p)
            p.until("!!document.querySelector('#word-import-dialog [data-add]')", "the preview")
            p.key("Enter", code="Enter", vk=13)                          # Enter in the box is the Add button
            p.until("!document.querySelector('#word-import-dialog')", "added")
            self.assertEqual(self.sent[1][1]["accept"], "all")
            after = self.counts()
            self.assertEqual((after["actions"] - before["actions"], after["raid"] - before["raid"], after["decisions"] - before["decisions"]), (2, 1, 1))
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("/Put back/.test(document.querySelector('.toast .toast-text').textContent)", "undone")
            self.assertEqual(self.counts(), before)

    def test_closing_the_preview_adds_nothing_and_the_same_file_can_be_read_again(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp, edit=True)
            before = self.counts()
            self.open_import(p)
            self.read_it(p)
            p.until("!!document.querySelector('#word-import-dialog [data-add]')", "the preview")
            p.js("document.querySelector('[data-cancel]').click()")
            p.until("!document.querySelector('#word-import-dialog')", "Cancel closed it")
            self.assertEqual(self.focus_is(p), "profile-btn")
            self.open_import(p)
            self.read_it(p)
            p.until("!!document.querySelector('#word-import-dialog [data-add]')", "the preview again")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#word-import-dialog')", "Esc closed it")
            self.assertEqual(self.counts(), before, "closing is not a choice to add")
            self.assertNotIn("apply", [r["op"] for k, r in self.sent if k == "import"], "the page never asked to add")
            self.assertEqual(self.database("SELECT count(*) AS n FROM change_log WHERE via = 'word'")[0]["n"], 0)

    def test_a_file_that_is_not_a_word_file_is_refused_in_words_and_nothing_is_added(self):
        for w, scheme in ((1400, "light"), (900, "dark")):
            with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                self.start()
                p = self.page(cdp, w, scheme, edit=True)
                before = self.counts()
                self.open_import(p)
                self.read_it(p, b"this is only some plain text, not a Word file at all", "notes.docx")
                p.until("!!document.querySelector('#word-msg .error')", "the refusal was shown")
                said = self.msg(p)
                self.assertIn("notes.docx", said)
                self.assertNotRegex(said, JARGON)
                self.assertEqual(p.js("document.querySelector('#word-msg').getAttribute('role')"), "alert")
                self.assertFalse(p.js("!!document.querySelector('#word-import-dialog [data-add]')"), "no preview, nothing to add")
                self.assertTrue(p.js("document.querySelector('[data-read]').disabled"), "choose another file to go on")
                self.assertEqual(self.counts(), before)
                self.assertEqual(self.sent[-1][1]["op"], "check")
                self.inside(p, "word-import-dialog")
                self.colours(p, "word-import-dialog", scheme)

    def test_a_file_over_the_limit_is_refused_in_words_before_it_is_sent(self):
        for w, scheme in ((1400, "dark"), (900, "light")):
            with self.subTest(width=w, scheme=scheme), chrome() as cdp:
                self.start()
                p = self.page(cdp, w, scheme, edit=True)
                self.open_import(p)
                p.js("""(function(){var dt=new DataTransfer(); dt.items.add(new File([new ArrayBuffer(26*1024*1024)], 'big report.docx'));
                    var el=document.querySelector('#word-file'); el.files=dt.files; el.dispatchEvent(new Event('change',{bubbles:true}))})()""")
                p.until("!!document.querySelector('#word-msg .error')", "the refusal was shown")
                self.assertEqual(self.msg(p), "big report.docx is more than 25 MB, more than clark will open. Save a smaller copy, or split it into two files, then choose it again.")
                self.assertTrue(p.js("document.querySelector('[data-read]').disabled"), "it cannot be read")
                self.assertEqual(self.sent, [], "nothing was sent: the page refused it")
                self.inside(p, "word-import-dialog")

    def test_a_file_with_nothing_new_says_so_and_offers_only_close(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp, edit=True)
            self.open_import(p)
            from test_docx_read import P
            self.read_it(p, docx(P("Weekly notes", style="Heading1") + P("Just some words")))
            p.until("!!document.querySelector('#word-count')", "the answer")
            text = self.text(p, "word-import-dialog")
            self.assertIn("Nothing new was found in week notes.docx.", text)
            self.assertIn("Nothing new was found. Put actions, risks, issues or decisions under a heading with that name.", text)
            self.assertFalse(p.js("!!document.querySelector('#word-import-dialog [data-add]')"), "nothing to add")
            self.assertEqual(p.js("document.querySelector('[data-cancel]').innerText"), "Close")
            self.assertEqual(self.sent[-1][1]["op"], "check")
            self.assertEqual(self.database("SELECT count(*) AS n FROM change_log WHERE via = 'word'")[0]["n"], 0)

    def test_busy_is_said_in_words(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp, edit=True)
            held = self.rig.httpd.word_import
            self.gate = threading.Event()
            self.addCleanup(self.gate.set)

            def slow(req):
                if req.get("op") == "check":
                    self.gate.wait(20)
                return held(req)
            self.rig.httpd.word_import = slow
            self.open_import(p)
            self.read_it(p)
            p.until("/Reading the file/.test(document.querySelector('#word-msg').innerText)", "it says it is reading")
            self.assertEqual(p.js("document.querySelector('#word-import-dialog').getAttribute('aria-busy')"), "true")
            self.assertTrue(p.js("document.querySelector('[data-read]').disabled && document.querySelector('[data-cancel]').disabled && document.querySelector('#word-file').disabled"))
            p.key("Escape", code="Escape", vk=27)
            self.assertTrue(p.js("!!document.querySelector('#word-import-dialog')"), "Esc does not close it while it reads")
            self.gate.set()
            p.until("!!document.querySelector('#word-import-dialog [data-add]')", "the preview")
            self.assertEqual(p.js("document.querySelector('#word-import-dialog').getAttribute('aria-busy')"), "false")

    def test_a_plan_that_has_gone_is_said_and_the_file_is_asked_for_again(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp, edit=True)
            before = self.counts()
            self.open_import(p)
            self.read_it(p)
            p.until("!!document.querySelector('#word-import-dialog [data-add]')", "the preview")
            word_route.PLANS.clear()                                     # the server forgot it (it waits 30 minutes)
            p.js("document.querySelector('#word-import-dialog [data-add]').click()")
            p.until("!!document.querySelector('#word-file') && !!document.querySelector('#word-msg .error')", "back to the file, with the words")
            self.assertEqual(self.msg(p), word_route.EXPIRED)
            self.assertEqual(self.counts(), before)

    def test_the_keyboard(self):
        with chrome() as cdp:
            self.start()
            p = self.page(cdp, edit=True)
            self.menu(p)
            p.js("document.querySelector('#profile-menu [data-kind=word-import]').focus()")
            p.key("Enter", code="Enter", vk=13)
            p.until("!!document.querySelector('#word-import-dialog[open]')", "Enter on the entry opened the box")
            p.until("document.activeElement && document.activeElement.id === 'word-file'", "focus starts on the picker")
            self.assertTrue(p.js("document.querySelector('#word-file').tagName === 'INPUT' && document.querySelector('#word-file').type === 'file'"), "a real file input")
            p.key("Tab", code="Tab", vk=9)
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-cancel')"), "Tab goes on to Cancel (Read the file waits for a file)")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#word-import-dialog')", "Esc cancels")
            self.assertEqual(self.focus_is(p), "profile-btn")
            self.open_import(p)
            self.read_it(p)
            p.until("!!document.querySelector('#word-import-dialog [data-add]')", "the preview")
            self.assertTrue(p.js("document.activeElement.hasAttribute('data-add')"), "focus is on Add")
            p.js("document.querySelector('.wi-item input[data-n=\"1\"]').focus()")
            p.key(" ", code="Space", vk=32)
            p.until("document.querySelector('#word-import-dialog [data-add]').innerText === 'Add 3 items'", "Space unticks an item")


# ── View and the published file have none of it ─────────────────────────────────────

class NotInView(unittest.TestCase):
    def test_the_published_page_has_none_of_the_new_strings_or_code(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for never in NEW_STRINGS + ("wordApi", "wordState", "changeWord", "wordSteps"):
            self.assertNotIn(never, view, never)

    def test_the_served_page_has_them(self):
        served = page.PAGE.read_text(encoding="utf-8")
        for need in ("/api/word-export", "/api/word-import", "Export to Word", "Import from Word", "Also a Word document", "word-export-dialog", "word-import-dialog"):
            self.assertIn(need, served, need)

    def test_no_file_outside_edit_names_the_word_routes(self):
        named = [str(f.relative_to(PAGE_SRC)) for f in PAGE_SRC.rglob("*") if f.suffix in (".js", ".jsx") and "/api/word-" in f.read_text(encoding="utf-8")]
        self.assertEqual(named, ["edit/wordApi.js"], "one file names them, and it is in edit/")
        for f in PAGE_SRC.rglob("*"):
            if f.suffix in (".js", ".jsx") and "edit" not in f.parts and f.name not in ("changes.js",):
                self.assertNotIn("wordApi", f.read_text(encoding="utf-8"), str(f))

    def test_a_published_file_holds_none_of_it(self):
        from test_publish_route import Rig as PublishRig

        class Case(unittest.TestCase):
            def runTest(self):
                pass
        case = Case()
        rig = PublishRig(case)
        try:
            status, got = rig.publish()
            self.assertEqual((status, got["ok"]), (200, True), got)
            published = (rig.local / "chosen.html").read_text(encoding="utf-8")
            for never in NEW_STRINGS:
                self.assertNotIn(never, published, never)
        finally:
            case.doCleanups()


# ── The words ────────────────────────────────────────────────────────────────────────

SOURCES = ("Word.jsx", "WordClash.jsx", "wordApi.js", "wordState.js")
QUOTED = re.compile(r'"((?:[^"\\\n]|\\.)+)"|`((?:[^`\\\n]|\\.)+)`')


def person_words():
    """Every sentence a person can read in the Word screens: the strings in their source, and the text in their JSX."""
    out = []
    for name in SOURCES:
        text = (PAGE_SRC / "edit" / name).read_text(encoding="utf-8")
        text = re.sub(r"^\s*//.*$", "", text, flags=re.M)
        for m in QUOTED.finditer(text):
            s = m.group(1) or m.group(2)
            if re.search(r"[A-Za-z]{3,}\s+[A-Za-z]{2,}", s) and not re.search(r"[#.\[\]=>:_]{2}|^(\s|[.#]|/api|document|[a-z-]+:)|querySelector|\bclass\b", s):
                out.append((name, s))
        out += [(name, t.strip()) for t in re.findall(r">([^<>{}]*[A-Za-z]{3,}[^<>{}]*)<", text)]
    return out


THINGS = {"Word", "Excel", "Edit", "Settings", "To", "MB", "Add", "Replace", "Cancel", "Close", "Undo", "OK"}      # the names of things on the page that a sentence may carry in capitals


class Words(unittest.TestCase):
    def test_there_are_words_to_read(self):
        got = [s for _, s in person_words()]
        for need in ("Export to Word", "Read the file", "Replace it", "Saving the Word report…", "Import from Word"):
            self.assertTrue(any(need in s for s in got), need)

    def test_none_starts_with_the_product_name_names_a_person_or_a_date_or_has_jargon(self):
        for name, s in person_words():
            s = re.sub(r"\$\{[^}]*\}", "x", s)
            self.assertNotRegex(s, r"^clark\b", f"{name}: {s!r} starts with the product name")
            self.assertNotRegex(s, r"(?:[.!?]\s+)clark\s+[A-Z]", f"{name}: {s!r} starts a sentence with the product name")
            self.assertNotRegex(s, JARGON, f"{name}: {s!r}")
            self.assertNotIn("!", s, f"{name}: {s!r}")
            self.assertNotRegex(s, r"\b\d{4}-\d\d-\d\d\b|\b\d\d-\d\d-\d{4}\b", f"{name}: {s!r} holds a date")
            inside = re.sub(r"(^|[.!?…]\s+)[A-Z][A-Za-z]*", " ", s)           # the first word of each sentence may be capital; any other must be a name of a thing
            self.assertEqual([w for w in re.findall(r"\b[A-Z][A-Za-z]*\b", inside) if w not in THINGS], [], f"{name}: {s!r} has a capital word that is not a name of a thing on the page")
            self.assertNotRegex(s, r"\bclark\b.*\bclark\b.*\bclark\b")

    def test_every_refusal_the_page_makes_for_itself_says_what_to_do_next(self):
        from re import search
        src = (PAGE_SRC / "edit" / "wordState.js").read_text(encoding="utf-8") + (PAGE_SRC / "edit" / "wordApi.js").read_text(encoding="utf-8")
        for const in ("READ_FAILED", "ADD_FAILED", "EXPORT_FAILED", "EMPTY", "UNREADABLE"):
            m = search(const + r' = "([^"]+)"', src)
            self.assertTrue(m, const)
            self.assertRegex(m.group(1), r"(Choose|Try|Check|Look|Reload|restart|again)", f"{const} says what to do")
            self.assertNotRegex(m.group(1), JARGON)
        self.assertIn("Save a smaller copy, or split it into two files, then choose it again.", src, "the over-size words are the server's own")
        m = re.search(r'tooBig = \(name\) => `([^`]+)`', src)
        self.assertEqual(m.group(1).replace("${name}", "N").replace("${WORD_FILE_MB}", "25"),
                         "N is more than 25 MB, more than clark will open. Save a smaller copy, or split it into two files, then choose it again.")


if __name__ == "__main__":
    unittest.main()
