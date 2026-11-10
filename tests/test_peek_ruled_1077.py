"""Row 1077, the four rulings: (1) the Draft chip is gone from every peek and the draftFor helper with it; (2) the client's work item
peek shows Source on the live Dashboard in View, and a published file never has it; (3) the words box is headed "Ask clark to update
for you"; (4) a client's peek (the Dashboard in View, and a published file) is the editor's, read only: no button, box or editable text
among its fields, and the same field rows as the editor's, less the two rows that are themselves controls (Shown to client, Client wording).
Run: python3 dev/run_tests.py test_peek_ruled_1077

The source and the built pages are read first (no browser); then the page in headless Chrome at 1400 and 900 px.
"""
import json
import tempfile
import unittest
from pathlib import Path

from _editor_checks import for_url
from _paths import ROOT
import _publish_fixture as fx
import _testpage as testpage

from clark import page  # noqa: E402
from _real_server import real_server  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402
import test_publish as tp  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
LABEL = "Ask clark to update for you"
OLD_LABEL = "Change an item with words"
EDIT_ONLY_ROWS = ("Shown to client", "Client wording")            # the two rows that are controls, not fields: the editor's alone
CONTROLS = "button, input, textarea, select, [contenteditable], [role=textbox], [role=combobox]"
ACTION, MILESTONE = "TUL-A-001", "TUL-M-002"


def code_files():
    return [p for p in SRC.rglob("*") if p.is_file() and p.suffix in (".js", ".jsx", ".css") and p.parent != SRC / "help"]


class Source(unittest.TestCase):
    def test_the_draft_chip_and_its_helper_are_gone(self):
        """Ruling 1: no Draft on any peek. The pill, its hook, its CSS and the helper that wrote its words are gone from the source and the page."""
        latest = (SRC / "edit" / "PeekLatest.jsx").read_text(encoding="utf-8")
        helper = (SRC / "edit" / "peekLatest.js").read_text(encoding="utf-8")
        for marker in ("draftFor", "pk-draft", "Draft", 'place: "draft"', "drafted"):
            self.assertNotIn(marker, latest, marker)
        self.assertNotIn("draftFor", helper)
        self.assertNotIn("Draft", (SRC / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8"), "the milestone peek has none either")
        self.assertNotIn("pk-draft", (SRC / "edit" / "edit.css").read_text(encoding="utf-8"))
        for f in code_files():
            self.assertNotIn("draftFor", f.read_text(encoding="utf-8"), str(f))
        built = page.PAGE.read_text(encoding="utf-8")
        for marker in ("pk-draft", "draftFor", "Latest update drafted"):
            self.assertNotIn(marker, built, marker)

    def test_the_words_box_is_headed_ask_clark_to_update_for_you(self):
        """Ruling 3: the heading and the section's label are the new words, and the old words are in no code (Help keeps its topic title)."""
        jsx = (SRC / "edit" / "SneakPeek.jsx").read_text(encoding="utf-8")
        self.assertIn(f'aria-label="{LABEL}"', jsx)
        self.assertIn(f"<span>{LABEL}</span>", jsx)
        for f in code_files():
            self.assertNotIn(OLD_LABEL, f.read_text(encoding="utf-8"), str(f))
        built = page.PAGE.read_text(encoding="utf-8")
        self.assertIn(LABEL, built)
        self.assertEqual(built.count(OLD_LABEL), built.count(OLD_LABEL + " (Sneak peek)"), "the old words are in the served page only as Help's topic title")
        self.assertNotIn(LABEL, page.VIEW_PAGE.read_text(encoding="utf-8"), "the words box is Edit only: a published file has no such words")

    def test_help_keeps_the_topic_title_and_its_first_step_names_the_box_as_the_page_does(self):
        topics = json.loads((SRC / "help" / "helpContent.json").read_text(encoding="utf-8"))["howto"]["tasks"]
        t = next(x for x in topics if x["id"] == "change-an-item-in-words")
        self.assertEqual(t["t"], "Change an item with words (Sneak peek)")
        self.assertIn(LABEL, t["s"][0])
        self.assertNotIn(OLD_LABEL, json.dumps(t["s"]), "the steps name the box as the page labels it")

    def test_source_is_the_live_pages_and_never_a_files(self):
        """Ruling 2: the Source line is handed to the peek on the live page (Edit, and the Dashboard in View), never from a file."""
        peek = (SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("const Source = !!tools && !fromFile.value && forItem && tools.PeekSource", peek)
        self.assertNotIn("data-pk-source", peek, "the line itself stays in the Edit part (edit/PeekActivity.jsx)")
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        for marker in ("data-pk-source", "pk-source", "/api/activity"):
            self.assertNotIn(marker, view, marker)


class Browser(unittest.TestCase):
    def setUp(self):
        self.store, folder, self.ids = load_demo()
        self.code = next(iter(self.ids))

        def cleanup(store=self.store):
            store.close()
            import shutil
            shutil.rmtree(str(folder), ignore_errors=True)
        self.addCleanup(cleanup)

    def live(self, cdp, width, store, hash_):
        projects = store.read("projects")
        s = real_server(store.path, store.data_for, who="Demo User", projects=lambda archived=False: projects, page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/{hash_}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1", 30), "the page drew")
        return sid

    def dashboard_in_view(self, cdp, width, store, code):
        sid = self.live(cdp, width, store, f"#dashboard&p={code}")
        self.assertTrue(wait(lambda: cdp.js("(r => !!r && r.dataset.mode === 'view')(document.querySelector('#report'))", sid)), "the Dashboard opens in View")
        return sid

    def to_edit(self, cdp, sid):
        cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#report').dataset.mode", sid) == "edit"))

    def open_peek(self, cdp, sid, ref, kind):
        cdp.js(f"clarkPage.openPeek({json.dumps(ref)}, {json.dumps(kind)})", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)), "the peek drew its fields")

    @staticmethod
    def labels(cdp, sid):
        return cdp.js("[...document.querySelectorAll('#peek .pk-fields dt')].map(d => d.textContent.trim())", sid)

    def no_controls(self, cdp, sid, where):
        found = cdp.js(f"[...document.querySelectorAll('#peek .pk-fields').at(-1).querySelectorAll({json.dumps(CONTROLS)})].map(e => e.outerHTML.slice(0, 80))", sid)
        self.assertEqual(found, [], f"a client's fields are read only ({where})")

    def no_draft(self, cdp, sid, where):
        self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-draft], #peek .pk-draft')", sid), where)
        self.assertEqual(cdp.js("[...document.querySelectorAll('#peek button, #peek .pk-chip, #peek .tag')].map(e => e.textContent.trim()).filter(t => t === 'Draft')", sid), [], where)

    def test_the_client_work_item_peek_is_the_editors_read_only_with_source(self):
        """Rulings 1, 2 and 4 on the live Dashboard: View shows the fields read only, with Source; Edit shows the same rows plus its two control rows."""
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                self.open_peek(cdp, sid, ACTION, "item")
                self.assertTrue(wait(lambda: cdp.js("(s => !!s && s.textContent.startsWith('Source: ') && s.textContent.length > 8)(document.querySelector('#peek [data-pk-source]'))", sid)),
                                "a client sees where the item came from on the live Dashboard in View: " + str(cdp.js("(s => s && s.textContent)(document.querySelector('#peek [data-pk-source]'))", sid)))
                self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-source] .pk-source-l').textContent", sid), "Source")
                self.no_controls(cdp, sid, "View")
                self.no_draft(cdp, sid, "View")
                for sel in (".pk-tabs", "[data-sneak]", "[data-pk-latest]", "[data-pk-title-in]", "[data-pk-needed]"):
                    self.assertFalse(cdp.js(f"!!document.querySelector('#peek {sel}')", sid), f"{sel} is the editor's alone")
                client = self.labels(cdp, sid)
                self.assertTrue(len(client) >= 6, client)
                self.to_edit(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-tabs')", sid)), "Edit: the tabs are drawn")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-source]')", sid)), "Edit keeps Source")
                self.assertTrue(cdp.js(f"document.querySelector('#peek .pk-fields').querySelectorAll({json.dumps(CONTROLS)}).length > 0", sid), "the editor's fields are controls")
                editor = self.labels(cdp, sid)
                self.assertEqual(client, [l for l in editor if l not in EDIT_ONLY_ROWS], "the client's rows are the editor's, in the editor's order")
                self.assertEqual(sorted(set(editor) - set(client)), sorted(EDIT_ONLY_ROWS), "the editor adds its two control rows and nothing else")
                self.no_draft(cdp, sid, "Edit")
                self.assertTrue(cdp.js("!!document.querySelector('#peek [data-pk-latest] [data-rich=latest_update]')", sid), "the Latest update stays, without its Draft")

    def test_the_client_milestone_peek_is_read_only_and_no_peek_has_a_draft(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.dashboard_in_view(cdp, width, self.store, self.code)
                self.open_peek(cdp, sid, MILESTONE, "milestone")
                self.assertFalse(cdp.js("!!document.querySelector('#peek [data-ms-edit]')", sid), "View: the milestone's fields, not its editor")
                self.no_controls(cdp, sid, "View, milestone")
                self.no_draft(cdp, sid, "View, milestone")
                self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-source]')", sid), "Source is a work item's line (Peek.jsx forItem)")
                self.to_edit(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-ms-edit]')", sid)), "Edit: the milestone editor")
                self.no_draft(cdp, sid, "Edit, milestone")

    def test_the_words_box_is_headed_by_the_new_label_on_the_page(self):
        with chrome() as cdp:
            sid = self.live(cdp, 1400, self.store, f"#work&p={self.code}")
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
            self.open_peek(cdp, sid, ACTION, "item")
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-close')", sid)))
            for _ in range(2):
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
                cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "/", "code": "Slash", "windowsVirtualKeyCode": 191}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-sneak]')", sid)), "two slashes open the box")
            self.assertEqual(cdp.js("document.querySelector('[data-sneak]').getAttribute('aria-label')", sid), LABEL)
            self.assertEqual(cdp.js("document.querySelector('[data-sneak] .sn-head').textContent.trim()", sid), LABEL)
            self.assertNotIn(OLD_LABEL, cdp.js("document.querySelector('#peek').textContent", sid))

    def test_the_published_peek_has_no_source_no_control_and_the_editors_rows(self):
        """Rulings 2 and 4 in a published file: the same rows as the editor shows for the same item (the plant in a real store), read only, and no Source."""
        _plant, _pub, text = tp.made()
        folder = Path(tempfile.mkdtemp(prefix="clark-1077-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        store = fx.build_db(folder / "clark.db")
        self.addCleanup(store.close)
        for width in (1400, 900):
            with self.subTest(width=width, where="editor"), chrome() as cdp:
                sid = self.dashboard_in_view(cdp, width, store, "PUB")
                self.to_edit(cdp, sid)
                self.open_peek(cdp, sid, "PUB-A-001", "item")
                editor = self.labels(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-pk-source]')", sid)), "the editor has Source")
            with self.subTest(width=width, where="file"), chrome() as cdp:
                path = folder / "report.html"
                path.write_text(text, encoding="utf-8")
                sid = tp.opened(cdp, path.as_uri() + "#work&p=PUB&item=PUB-A-001", width)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)), "the published peek drew")
                self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-source], #peek .pk-source')", sid), "a file has no Source line")
                self.assertNotIn("Source", self.labels(cdp, sid))
                self.assertNotIn("Source:", cdp.js("document.querySelector('#peek').textContent", sid))
                self.no_controls(cdp, sid, "published file")
                self.no_draft(cdp, sid, "published file")
                published = self.labels(cdp, sid)
                self.assertEqual(published, [l for l in editor if l not in EDIT_ONLY_ROWS], "the published rows are the editor's, read only")
                self.assertEqual(sorted(set(editor) - set(published)), sorted(EDIT_ONLY_ROWS))
                # the milestone peek in the same file: fields only, nothing to press
                cdp.js("location.hash = '#dashboard&p=PUB&ms=PUB-M-001'", sid)
                self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek === 'PUB-M-001')(document.querySelector('#peek'))", sid)), "the milestone peek drew")
                self.no_controls(cdp, sid, "published file, milestone")
                self.no_draft(cdp, sid, "published file, milestone")


if __name__ == "__main__":
    unittest.main()
