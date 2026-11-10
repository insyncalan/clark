"""Row 1078 (the owner's rulings, 09-11 and 10-11-2026): the milestone peek in the work item peek's format. One flat surface, no tiles: a
header line under the title says the state, the owner and the progress (the chip reads Achieved, with its date, only when the milestone
is achieved; picking Achieved sets the progress to 100); the rows are Description, Agreed date, Forecast date, Workstream, Visible to
client (the editor's alone) and Client wording, label left and value right with a hairline between; the name is the title, edited in place;
Description and Client wording are on the one rich editor (#1005). A client (the Dashboard in View, a published file) sees the same peek
read only, less the Visible to client row, and a published file never carries the editor's words.
Run: python3 dev/run_tests.py test_milestone_peek_1078

Without a browser: the sources, the built pages, publish.select and the change route. With headless Chrome (fails, never skips, without it):
the Milestones page, the Dashboard in View and a published file, at 1400 and 900 px, light and dark.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
import _publish_fixture as fx

from clark import changes, excel, page, publish  # noqa: E402
from test_movement_page import GO_LIVE, PILOT, Base  # noqa: E402
from test_server import chrome  # noqa: E402
import test_publish as tp  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
EDITOR_ROWS = ["Description", "Agreed date", "Forecast date", "Workstream", "Visible to client", "Client wording"]
CLIENT_ROWS = [r for r in EDITOR_ROWS if r != "Visible to client"]
EDIT_ONLY = ("Visible to client", "data-ms-edit", "pk-ms-states", "data-ms-states", '"data-ms-field"', "data-ms-in")     # words and hooks of the editor's module alone
CONTROLS = "button, input, textarea, select, [contenteditable], [role=textbox], [role=combobox], [role=button]"
LABELS = "[...document.querySelectorAll('#peek .pk-fields dt')].map(d => d.textContent.trim())"
WORDS = "((e) => { const c = e.cloneNode(true); c.querySelectorAll('.av, .sr').forEach(x => x.remove()); return c.textContent.trim(); })"     # what is read: not the owner's initials picture, not the screen reader's prefix
HEAD = "(() => { const h = document.querySelector('#peek [data-ms-head]'); return h ? [...h.children].filter(e => !e.classList.contains('pk-ms-sep')).map(e => e.dataset.msHead || e.className) : null; })()"
TILES = """(() => { const out = []; for (const r of document.querySelectorAll('#peek .pk-fields .pk-row')) { const c = getComputedStyle(r);
  const dt = r.querySelector('dt').getBoundingClientRect(), dd = r.querySelector('dd').getBoundingClientRect();
  out.push({ row: r.querySelector('dt').textContent.trim(), left: c.borderLeftWidth, right: c.borderRightWidth, bottom: c.borderBottomWidth, top: c.borderTopWidth,
             radius: c.borderTopLeftRadius, bg: c.backgroundColor, beside: dt.right <= dd.left + 1 && Math.abs(dt.top - dd.top) < 4 }); } return out; })()"""


class Sources(unittest.TestCase):
    def test_the_editor_draws_the_rows_in_the_ruled_order_with_the_name_as_the_title(self):
        src = (PAGE_SRC / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8")
        order = [m.group(1) for m in re.finditer(r'<Row name="([^"]+)"', src)]
        self.assertEqual(order, ["Description", "Agreed date", "Forecast date", "Achieved on", "Workstream", "Visible to client", "Client wording"])
        self.assertIn("export function MilestoneTitle", src, "the name is the title, edited in place")
        self.assertNotIn('<Row name="Name"', src)
        self.assertNotIn('<Row name="Milestone"', src, "no Milestone row: the title is the name (ruled)")
        self.assertIn('data-ms-row={k}', src, "the editor's rows are plain rows, never the four property cells (data-row)")
        self.assertNotIn('data-row={k}', src)
        self.assertIn('<RichField field="client_message"', src, "Client wording is on the one rich editor (ruled)")
        self.assertNotIn('field="client_message" label="Client wording" value', src, "not a plain box any more")
        self.assertIn("MilestoneTitle", (PAGE_SRC / "edit" / "index.js").read_text(encoding="utf-8"))

    def test_the_shared_fields_are_the_same_rows_read_only_with_the_header_line(self):
        src = (PAGE_SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        body = src[src.index("function MilestoneFields"):]
        body = body[:body.index("\n}\n")]
        self.assertEqual([m.group(1) for m in re.finditer(r'<Row name="([^"]+)"', body)], CLIENT_ROWS)
        self.assertNotIn("Visible to client", src, "the editor's row is in the editor's module alone (published page)")
        self.assertIn("data-ms-head", src)
        self.assertIn("MilestoneTitle", src)
        self.assertNotIn("dangerouslySetInnerHTML", src, "rich words go through the one audited seam (CleanProse)")

    def test_achieved_sets_the_progress_to_100(self):
        src = (PAGE_SRC / "edit" / "msPeek.js").read_text(encoding="utf-8")
        self.assertIn('return { status: "Done", state: "Achieved", state_set: 1, actual_date: m.actual_date || today, percent_complete: 100 };', src)

    def test_the_published_page_has_the_header_line_and_none_of_the_editors_words(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        for marker in ("data-ms-head", ".pk-ms-head {", "data-ms-fields"):
            self.assertIn(marker, view, marker)
        for word in EDIT_ONLY:
            self.assertNotIn(word, view, word)
        self.assertNotIn(".pk-ms-head {", (PAGE_SRC / "edit" / "edit.css").read_text(encoding="utf-8"), "the shared look is shell.css's (inlined into the published page)")
        self.assertIn(".pk-ms-head {", (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8"))

    def test_the_client_wording_of_a_milestone_is_rich_on_publish_in_the_sheet_and_in_the_change_route(self):
        self.assertIn("client_message", publish.RICH["milestones"])
        self.assertIn(("milestones", "client_message"), publish.LEGACY_RICH)
        self.assertIn(("milestones", "client_message"), excel.RICH_WORDS)
        got = changes._checked_milestone_changes({"client_message": " Plain <words> "})
        self.assertEqual(got, {"client_message": "Plain <words>"}, "plain text from any other caller is stored as typed (an older row reads as paragraphs)")
        with self.assertRaises(changes.Refused):
            changes._checked_milestone_changes({"client_message": "Plain\nwords"})           # as it always was (test_movement_hostile)
        got = changes._checked_milestone_changes({"client_message": "<p>Rich <strong>words</strong></p><script>x()</script>"})
        self.assertEqual(got, {"client_message": "<p>Rich <strong>words</strong></p>"}, "the editor's HTML is cleaned")
        self.assertEqual(changes._checked_milestone_changes({"client_message": "<p> </p>"}), {"client_message": None})
        with self.assertRaises(changes.Refused):
            changes._checked_milestone_changes({"client_message": "<p>" + "w" * 501 + "</p>"})
        # publish: the file carries the cleaned HTML (or an old plain text made into paragraphs), the template words stay words
        def rich(plant):
            for m in plant["data"]["milestones"]:
                if m["id"] == "PUB-M-001":
                    m["client_message"] = "<p>Keep <em>this</em></p><script>x()</script>"
                if m["id"] == "PUB-M-002":
                    m["client_message"] = "Old & plain\nLines"
        _plant, pub, text = tp.made(rich)
        by = {m["id"]: m for m in pub["data"]["milestones"]}
        self.assertEqual(by["PUB-M-001"]["client_message"], "<p>Keep <em>this</em></p>")
        self.assertEqual(by["PUB-M-002"]["client_message"], "<p>Old &amp; plain</p><p>Lines</p>")
        self.assertNotIn("<script>x()", text)


class Fields(Base):
    """The Milestones page (Edit, always), the Dashboard in View and a published file."""
    cur = GO_LIVE

    def visit_peek(self, cdp, ms=GO_LIVE, width=1400, theme=None, view="milestones"):
        from test_report_editor import Pg
        self.cur = ms
        p = Pg.at(self, cdp, self.s.port, f"#{view}&p=ABC&ms={ms}")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("!!document.querySelector('#peek [data-ms-head]')", "the peek drew its header line")
        if theme:
            p.js(f"document.documentElement.dataset.theme = '{theme}'")
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
        p.until("document.getAnimations().length === 0", "no animation running")
        return p

    def click(self, p, sel):
        p.until(f"!!document.querySelector({json.dumps(sel)})", sel)
        p.js(f"document.querySelector({json.dumps(sel)}).click()")

    def until_store(self, test, seconds=10):
        import time
        end = time.time() + seconds
        while time.time() < end:
            if test():
                return True
            time.sleep(0.1)
        return test()

    def saved(self, p, field, value):
        self.assertTrue(self.until_store(lambda: self.row(self.cur)[field] == value), f"{field} was not saved as {value!r}: {self.row(self.cur)[field]!r}")

    def test_the_editor_has_the_header_line_the_ruled_rows_and_no_achieved_until_it_is(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp, ms=PILOT)          # Planned, far ahead: On track by the dates
            self.assertEqual(p.js(HEAD), ["state", "owner", "progress"], "one line: state, owner, progress")
            self.assertEqual(p.js(LABELS), EDITOR_ROWS)
            self.assertEqual(p.js("document.querySelectorAll('#peek h2.pk-title [data-ms-field=name]').length"), 1, "the name is the title, in place")
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-ms-edit] .pk-row')].map((r) => r.dataset.msRow)"),
                             ["description", "baseline", "forecast", "workstream", "visible", "client_message"])
            self.assertEqual(p.js("document.querySelector('#peek [data-ms-head=state]').textContent.trim()"), "On track")
            self.assertEqual(p.js(f"{WORDS}(document.querySelector('#peek [data-ms-head=owner]'))"), "Sam Example")
            self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-field=actual_date]').length"), 0, "no Achieved on row until it is achieved")
            self.assertNotIn("Achieved", p.js("document.querySelector('#peek [data-ms-head]').textContent"))
            self.assertEqual(p.js("document.querySelector('#peek [data-ms-head=progress] [data-ms-num]').value"), "", "no progress set yet")
            self.click(p, "#peek [data-ms-state=Achieved]")
            self.saved(p, "status", "Done")
            row = self.row(self.cur)
            self.assertEqual((row["state"], row["percent_complete"]), ("Achieved", 100), "Achieved sets the progress to 100 (the canvas's note)")
            p.until("/^Achieved on \\d\\d-\\d\\d-\\d{4}$/.test(document.querySelector('#peek [data-ms-head=state]').textContent.trim())", "the chip says Achieved with its date: "
                    + str(p.js("document.querySelector('#peek [data-ms-head=state]').textContent")))
            p.until("document.querySelector('#peek [data-ms-head=progress] [data-ms-num]').value === '100'", "the header shows 100")
            self.assertEqual(p.js(LABELS), ["Description", "Agreed date", "Forecast date", "Achieved on", "Workstream", "Visible to client", "Client wording"], "the Achieved on row comes with the state")
            self.assertEqual(self.sent[-1][1]["changes"]["percent_complete"], 100)

    def test_client_wording_is_the_one_rich_editor_with_one_undo(self):
        with chrome() as cdp:
            p = self.visit_peek(cdp)
            self.click(p, "#peek [data-ms-row=client_message] [data-rich=client_message]")
            p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened with the focus")
            self.assertEqual(p.js("document.querySelectorAll('#peek textarea[data-ms-in=client_message]').length"), 0, "not a plain box any more")
            p.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.insertContent('For the client'); true")
            p.key("Enter", modifiers=4 if p.js("/Mac/.test(navigator.platform)") else 2, code="Enter", vk=13)
            self.saved(p, "client_message", "<p>For the client</p>")
            self.assertEqual(self.sent[-1][1]["changes"], {"client_message": "<p>For the client</p>"})
            self.assertEqual(self.sent[-1][1]["place"], "peek")
            p.until("!document.querySelector('#peek .ProseMirror')", "the editor closed after the save")
            self.assertEqual(p.js("[...document.querySelectorAll('#peek [data-rich=client_message] p')].map((e) => e.textContent)"), ["For the client"])
            p.until("/^Client wording of ABC-M-002 changed\\.$/.test((document.querySelector('.toast .toast-text') || {}).textContent || '')", "the toast")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.saved(p, "client_message", None)

    def test_no_tile_anywhere_label_left_value_right_at_both_widths_in_both_themes(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit_peek(cdp, width=width, theme=theme)
                    rows = p.js(TILES)
                    self.assertEqual([r["row"] for r in rows], EDITOR_ROWS)
                    for r in rows:
                        self.assertEqual((r["left"], r["right"], r["bottom"], r["radius"], r["bg"]), ("0px", "0px", "0px", "0px", "rgba(0, 0, 0, 0)"), f"no tile: {r}")
                        self.assertEqual(r["top"], "1px", f"one hairline between rows: {r}")
                        self.assertTrue(r["beside"], f"label left, value right: {r}")
                    head = p.js("(() => { const h = document.querySelector('#peek [data-ms-head]'), c = getComputedStyle(h); const mids = [...h.querySelectorAll('[data-ms-head]')].map(e => { const r = e.getBoundingClientRect(); return r.top + r.height / 2; }); return { border: c.borderLeftWidth + c.borderRightWidth, bg: c.backgroundColor, spread: Math.max(...mids) - Math.min(...mids), inside: h.getBoundingClientRect().right <= document.querySelector('#peek').getBoundingClientRect().right + 1 }; })()")
                    self.assertEqual((head["border"], head["bg"]), ("0px0px", "rgba(0, 0, 0, 0)"), "the header is flat: " + str(head))
                    self.assertLess(head["spread"], 8, "the state, the owner and the progress are on one line: " + str(head))
                    self.assertTrue(head["inside"])
                    self.assertTrue(p.js("(p => p.scrollWidth <= p.clientWidth + 1)(document.querySelector('#peek'))"), "no sideways scroll")

    def test_the_dashboard_in_view_shows_the_same_peek_read_only_less_visible_to_client(self):
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", GO_LIVE, {"percent_complete": 40, "client_message": "<p>Going <strong>well</strong></p>", "description": "<p>Scope</p>"})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit_peek(cdp, width=width)
                editor_head = p.js(f"[...document.querySelectorAll('#peek [data-ms-head] [data-ms-head]')].map(e => e.dataset.msHead === 'progress' ? e.querySelector('[data-ms-num]').value + '%' : {WORDS}(e))")
                self.assertEqual(editor_head[2], "40%")
            with self.subTest(width=width, view="dashboard"), chrome() as cdp:
                p = self.visit_peek(cdp, width=width, view="dashboard")
                self.assertEqual(p.js("document.querySelectorAll('#peek [data-ms-edit], #peek [data-ms-states]').length"), 0, "View: the fields, not the editor")
                self.assertEqual(p.js(f"[...document.querySelector('#peek .pk-body').querySelectorAll({json.dumps(CONTROLS)})].map(e => e.outerHTML.slice(0, 60))"), [], "read only")
                self.assertEqual(p.js(HEAD), ["state", "owner", "progress"])
                self.assertEqual(p.js(f"[...document.querySelectorAll('#peek [data-ms-head] [data-ms-head]')].map({WORDS})"), editor_head, "the same header line as the editor's")
                self.assertEqual(p.js(LABELS), CLIENT_ROWS)
                self.assertEqual(p.js("document.querySelector('#peek [data-ms-fields] [data-ms-row=client_message] strong').textContent"), "well", "rich words, as the editor shows them")
                self.assertEqual(p.js("document.querySelector('#peek [data-ms-fields] [data-ms-row=description]').textContent.replace('Description', '').trim()"), "Scope")
                rows = p.js(TILES)
                self.assertEqual([r["row"] for r in rows], CLIENT_ROWS)
                for r in rows:
                    self.assertEqual((r["left"], r["radius"], r["bg"], r["beside"]), ("0px", "0px", "rgba(0, 0, 0, 0)", True), str(r))


class Published(unittest.TestCase):
    def test_a_published_file_has_the_same_peek_read_only_and_none_of_the_editors_words(self):
        def rich(plant):
            for m in plant["data"]["milestones"]:
                if m["id"] == "PUB-M-001":
                    m["client_message"] = "<p>Keep <em>this</em> ZQ-KEEP-MS-MESSAGE</p>"
                    m["description"] = "<p>ZQ-KEEP-MS-DESCRIPTION</p>"
                    m["percent_complete"] = 60
        plant = fx.load()
        rich(plant)
        pub = publish.select(fx.inputs(plant))
        text = publish.render(pub, page.page_html(tp.EMPTY_BRANDING, view=True), plant["as_at"], pub["data"]["project"]["name"])     # the view-only page, as publish.main writes a file (#65)
        for word in EDIT_ONLY:
            self.assertNotIn(word, text, word)
        folder = Path(tempfile.mkdtemp(prefix="clark-1078-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = tp.opened(cdp, path.as_uri() + "#dashboard&p=PUB&ms=PUB-M-001", width)
                from test_server import wait
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-ms-head]')", sid)), "the published milestone peek drew")
                self.assertEqual(cdp.js(HEAD, sid), ["state", "owner", "progress"])
                self.assertEqual(cdp.js("document.querySelector('#peek [data-ms-head=state]').textContent.trim()", sid), "At risk")
                self.assertEqual(cdp.js(f"{WORDS}(document.querySelector('#peek [data-ms-head=owner]'))", sid), "Delivery lead")
                self.assertEqual(cdp.js(f"{WORDS}(document.querySelector('#peek [data-ms-head=progress]'))", sid), "60%")
                self.assertEqual(cdp.js(LABELS, sid), CLIENT_ROWS, "the editor's rows, less Visible to client")
                self.assertEqual(cdp.js(f"[...document.querySelector('#peek .pk-body').querySelectorAll({json.dumps(CONTROLS)})].length", sid), 0, "read only")
                self.assertEqual(cdp.js("document.querySelector('#peek [data-ms-row=client_message] em').textContent", sid), "this")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-ms-row=client_message] script').length", sid), 0)
                for r in cdp.js(TILES, sid):
                    self.assertEqual((r["left"], r["radius"], r["bg"], r["beside"]), ("0px", "0px", "rgba(0, 0, 0, 0)", True), str(r))
                # a milestone with no client wording publishes no description (row 560) and has no wording to show: neither row is drawn (reader B), the others are
                cdp.js("location.hash = '#dashboard&p=PUB&ms=PUB-M-002'", sid)
                self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek === 'PUB-M-002')(document.querySelector('#peek'))", sid)))
                self.assertEqual(cdp.js(LABELS, sid), [r for r in CLIENT_ROWS if r not in ("Description", "Client wording")])
                self.assertEqual(cdp.js("document.querySelector('#peek [data-ms-head=progress]').textContent.trim()", sid), "Not set")


if __name__ == "__main__":
    unittest.main()
