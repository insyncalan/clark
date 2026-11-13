"""Row 1077, the rulings: (1) the Draft chip is gone from every peek and the draftFor helper with it; (2, as ruled on 10-11-2026) every
peek, work item or milestone, shows its Source by NAME (never a path): the live page in Edit and in View, and a published file too;
(3) the words box is headed "Ask clark to update for you"; (4) a client's peek (the Dashboard in View, and a published file) is the editor's,
read only: no button, box or editable text among its fields, and the same field rows as the editor's, less the two rows that are themselves
controls (Shown to client, Client wording); (5, ruled 10-11-2026) the peek is flat: the four property cells have no tile, a tab's focus is an
underline and not a box, the Latest update field has no box at rest or under the pointer, and the words box is a foot band pinned to the
bottom of the peek while its body scrolls; the flat cells reach the published peek too (shell.css is the published page's).
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
from clark.store import open_store  # noqa: E402
from _real_server import real_server  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402
import test_publish as tp  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
LABEL = "Ask clark to update for you"
OLD_LABEL = "Change an item with words"
EDIT_ONLY_ROWS = ("Shown to client", "Client wording")            # the two rows that are controls, not fields: the editor's alone
HISTORY_ROWS = ("Last reviewed",)                                  # worked out from the item's history on the live page; a published file carries no history
CONTROLS = "button, input, textarea, select, [contenteditable], [role=textbox], [role=combobox]"
ACTION, MILESTONE = "TUL-A-001", "TUL-M-002"
CELLS = "(() => { const out = {}; for (const k of ['status', 'priority', 'owner', 'due']) { const e = document.querySelector('#peek .pk-fields > [data-row=' + k + ']'); if (!e) continue; const c = getComputedStyle(e); out[k] = [c.borderTopWidth, c.borderLeftWidth, c.borderTopLeftRadius, c.backgroundColor, c.boxShadow]; } return out; })()"
FLAT = ["0px", "0px", "0px", "rgba(0, 0, 0, 0)", "none"]          # border, border, radius, fill, shadow
SECTIONS = "(() => { const out = {}; for (const s of ['.pk-bar', '.pk-title', '.pk-fields', '.pk-latest', '.pk-tabs', '.pk-source', '.pk-last']) { const e = document.querySelector('#peek ' + s); if (e) out[s] = getComputedStyle(e).boxShadow; } return out; })()"   # the peek's sections draw no shadow (only the panel itself does)
PROBE = "((name) => { const e = document.createElement('i'); e.style.cssText = 'border:1px solid var(' + name + ')'; document.body.appendChild(e); const c = getComputedStyle(e).borderTopColor; e.remove(); return c; })"


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

    def test_no_shown_help_text_mentions_the_draft_chip(self):
        """Ruling 1: the chip is gone, so Help neither names it in the peek's steps and parts nor draws its legend icon."""
        import sys
        sys.path.insert(0, str(ROOT / "tests"))
        from _help_shown import shown_content
        shown = json.dumps(shown_content(), ensure_ascii=False)
        raw = json.dumps(json.loads((SRC / "help" / "helpContent.json").read_text(encoding="utf-8")), ensure_ascii=False)
        for text, where in ((shown, "shown Help"), (raw, "the Help source")):
            self.assertNotIn("**Draft**", text, where)
            self.assertNotIn("writes one from the item", text, where)
            self.assertNotIn("Write the latest update from the item", text, where)

        def walk(o):
            if isinstance(o, list):
                if o[:2] == ["sparkle", "Draft"]:
                    yield o
                for x in o:
                    yield from walk(x)
            elif isinstance(o, dict):
                for x in o.values():
                    yield from walk(x)
        self.assertEqual(list(walk(json.loads(raw))), [], "the icon legend has no Draft entry")

    def test_the_foot_band_rule_is_the_editors_alone(self):
        """Rule 6 (fifth pass): `.peek .wordsbox` styles the Edit-only words box, so it is in edit.css and not in the published page."""
        self.assertIn(".peek .wordsbox", (SRC / "edit" / "edit.css").read_text(encoding="utf-8"))
        self.assertNotIn(".peek .wordsbox", (SRC.parent / "shell.css").read_text(encoding="utf-8"))
        self.assertNotIn(".peek .wordsbox", page.VIEW_PAGE.read_text(encoding="utf-8"))
        self.assertIn(".peek .wordsbox", page.PAGE.read_text(encoding="utf-8"))

    def test_the_placeholder_rule_is_the_editors_alone(self):
        """Rule 6: the words box is Edit only, so its placeholder colour is in edit.css and not in the published page."""
        self.assertIn(".sn-in::placeholder", (SRC / "edit" / "edit.css").read_text(encoding="utf-8"))
        self.assertNotIn(".sn-in::placeholder", (SRC.parent / "shell.css").read_text(encoding="utf-8"))
        self.assertNotIn(".sn-in::placeholder", page.VIEW_PAGE.read_text(encoding="utf-8"))
        self.assertIn(".sn-in::placeholder", page.PAGE.read_text(encoding="utf-8"))

    def test_source_is_read_live_on_the_page_and_carried_by_name_in_a_file(self):
        """Ruling 2 (10-11): on the live page the line comes from the server (Edit and View alike, items and milestones); a published file
        draws the name its data carries (publish.select, source_name) and never asks a server."""
        peek = (SRC / "components" / "Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("const Source = !!tools && !fromFile.value && tools.PeekSource", peek)
        self.assertIn("export function SourceLine", peek)
        self.assertIn("data-pk-source", peek)
        self.assertIn("SourceLine", (SRC / "edit" / "PeekActivity.jsx").read_text(encoding="utf-8"), "the Edit part draws the same line")
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        self.assertIn("data-pk-source", view)
        self.assertIn(".pk-source {", view, "its rule is the published page's (shell.css)")
        self.assertNotIn("/api/activity", view)
        self.assertNotIn(".pk-source {", (SRC / "edit" / "edit.css").read_text(encoding="utf-8"))


class Peeks(unittest.TestCase):
    """The demo store, a live server and the ways in; the tests are in Browser and Flat below."""
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
        found = cdp.js(f"(() => {{ const all = document.querySelectorAll('#peek .pk-fields'), f = all[all.length - 1]; return [...f.querySelectorAll({json.dumps(CONTROLS)})].map(e => e.outerHTML.slice(0, 80)); }})()", sid)
        self.assertEqual(found, [], f"a client's fields are read only ({where})")

    def no_draft(self, cdp, sid, where):
        self.assertFalse(cdp.js("!!document.querySelector('#peek [data-pk-draft], #peek .pk-draft')", sid), where)
        self.assertEqual(cdp.js("[...document.querySelectorAll('#peek button, #peek .pk-chip, #peek .tag')].map(e => e.textContent.trim()).filter(t => t === 'Draft')", sid), [], where)



class Browser(Peeks):
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
                self.assertTrue(wait(lambda: cdp.js("(s => !!s && s.textContent.startsWith('Source: ') && s.textContent.length > 8)(document.querySelector('#peek [data-pk-source]'))", sid)),
                                "a milestone has its Source too (ruling of 10-11)")
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

    def test_the_published_peek_shows_the_source_name_no_control_and_the_editors_rows(self):
        """Rulings 2 and 4 in a published file: the same rows as the editor shows for the same item (the plant in a real store), read only, and the
        Source by name: the plant's sources are paths (ZQ-SOURCE-PATH/actions.xlsx), so the file names the file and never the folder."""
        _plant, _pub, text = tp.made()
        self.assertNotIn("ZQ-SOURCE-PATH", text, "no path reaches a file")
        self.assertIn("actions.xlsx", text)
        folder = Path(tempfile.mkdtemp(prefix="clark-1077-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        store = open_store(fx.build_db(folder / "clark.db"), onedrive_roots=[])
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
                self.assertEqual(cdp.js("(s => s && s.textContent)(document.querySelector('#peek [data-pk-source]'))", sid), "Source: actions.xlsx", "the file's peek names the source file, not its path")
                self.assertNotIn("Source", self.labels(cdp, sid), "a line under the fields, not a field row")
                self.no_controls(cdp, sid, "published file")
                self.no_draft(cdp, sid, "published file")
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    cells = cdp.js(CELLS, sid)
                    self.assertEqual(sorted(cells), ["due", "owner", "priority", "status"])
                    self.assertEqual(set(map(tuple, cells.values())), {tuple(FLAT)}, f"the published cells are flat too, {theme} (ruling of 10-11): " + str(cells))
                    shadows = cdp.js(SECTIONS, sid)
                    self.assertTrue(shadows and set(shadows.values()) == {"none"}, f"no shadow on a published peek's sections, {theme}: " + str(shadows))
                published = self.labels(cdp, sid)
                self.assertEqual(published, [l for l in editor if l not in EDIT_ONLY_ROWS + HISTORY_ROWS], "the published rows are the editor's, read only")
                self.assertEqual(sorted(set(editor) - set(published)), sorted(EDIT_ONLY_ROWS + HISTORY_ROWS))
                self.assertIn("Raised", published, "the date raised is published, so its row stays")
                # the milestone peek in the same file: fields only, nothing to press
                cdp.js("location.hash = '#dashboard&p=PUB&ms=PUB-M-001'", sid)
                self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek === 'PUB-M-001')(document.querySelector('#peek'))", sid)), "the milestone peek drew")
                self.assertEqual(cdp.js("(s => s && s.textContent)(document.querySelector('#peek [data-pk-source]'))", sid), "Source: milestones.xlsx")
                self.no_controls(cdp, sid, "published file, milestone")
                self.no_draft(cdp, sid, "published file, milestone")

    def test_a_published_peek_with_no_source_name_draws_no_source_line(self):
        """A source that is free text publishes nothing (row 1077, ruling A): the peek then has no Source line at all, not an empty
        "Source:". Mutant: SourceLine drawn whether or not it has text."""
        def free_text(plant):
            for r in plant["data"]["actions"] + plant["data"]["milestones"]:
                r["source"] = "Added by hand in clark"
        _plant, _pub, text = tp.made(free_text)
        folder = Path(tempfile.mkdtemp(prefix="clark-1077-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = tp.opened(cdp, path.as_uri() + "#work&p=PUB&item=PUB-A-001", width)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)), "the published peek drew")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-source]').length", sid), 0, "an item with no source name has no Source line")
                cdp.js("location.hash = '#dashboard&p=PUB&ms=PUB-M-001'", sid)
                self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek === 'PUB-M-001')(document.querySelector('#peek'))", sid)), "the milestone peek drew")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields dt')", sid)))
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-source]').length", sid), 0, "a milestone with no source name has none either")


class Flat(Peeks):
    """Ruling 5 (10-11-2026), in Edit on the Work items page: no tile, no boxed tab focus, no box round the Latest update, a pinned foot band."""
    def work(self, cdp, width, height=900):
        sid = self.live(cdp, width, self.store, f"#work&p={self.code}")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 0))
        self.open_peek(cdp, sid, ACTION, "item")
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations({subtree: true}).every(a => a.playState !== 'running')", sid)), "the slide-in has ended")
        return sid

    def test_the_property_cells_are_flat_and_a_tabs_focus_is_an_underline(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.work(cdp, width)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    cells = cdp.js(CELLS, sid)
                    self.assertEqual(sorted(cells), ["due", "owner", "priority", "status"])
                    self.assertEqual(set(map(tuple, cells.values())), {tuple(FLAT)}, f"{theme}: " + str(cells))
                    shadows = cdp.js(SECTIONS, sid)
                    self.assertTrue(shadows and set(shadows.values()) == {"none"}, f"no shadow on the editor's peek sections, {theme}: " + str(shadows))
                cdp.js("document.documentElement.dataset.theme = 'light'", sid)
                # the Activity tab (not selected): a keyboard focus draws an underline in the focus colour and no outline box
                cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
                cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
                cdp.js("document.querySelector('#peek [data-pk-tab=activity]').focus()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.pkTab", sid) == "activity"))
                got = cdp.js("(() => { const e = document.activeElement, c = getComputedStyle(e); return [e.matches(':focus-visible'), c.outlineStyle, c.borderBottomWidth, c.borderBottomColor]; })()", sid)
                self.assertTrue(got[0], "the focus came from the keyboard: " + str(got))
                self.assertEqual(got[1], "none", "no box round the tab: " + str(got))
                self.assertEqual((got[2], got[3]), ("2px", cdp.js(f"{PROBE}('--focus')", sid)), "an underline in the focus colour: " + str(got))

    def test_the_latest_update_has_no_box_at_rest_or_under_the_pointer(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.work(cdp, width)
                sel = "#peek [data-pk-latest] [data-rich=latest_update]"
                self.assertTrue(cdp.js(f"!!document.querySelector({json.dumps(sel)})", sid), "the Latest update is drawn (Work items has no View)")
                look = f"(() => {{ const c = getComputedStyle(document.querySelector({json.dumps(sel)})); return [c.outlineStyle, c.outlineWidth, c.borderTopWidth, c.backgroundColor]; }})()"
                rest = cdp.js(look, sid)
                self.assertEqual((rest[0], rest[2], rest[3]), ("none", "0px", "rgba(0, 0, 0, 0)"), "at rest, plain text: " + str(rest))
                x, y = cdp.js(f"(() => {{ const r = document.querySelector({json.dumps(sel)}).getBoundingClientRect(); return [r.left + 20, r.top + r.height / 2]; }})()", sid)
                cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(sel)}).matches(':hover')", sid)), "the pointer is over it")
                hover = cdp.js(look, sid)
                self.assertEqual((hover[0], hover[2]), ("none", "0px"), "under the pointer, no box: " + str(hover))
                self.assertEqual(hover[3], cdp.js(f"{PROBE}('--grey-50')", sid), "a quiet tint says it can be edited: " + str(hover))

    def test_the_words_box_placeholder_reads_at_4_5_to_1_in_light_and_dark(self):
        """The browser's default placeholder colour was 3.14:1 in dark: the input's placeholder uses the muted text token."""
        probe = ("(() => { const i = document.querySelector('#peek .sn-in'), rgb = (c) => (c.match(/[\\d.]+/g) || []).map(Number).slice(0, 3);"
                 " return [rgb(getComputedStyle(i, '::placeholder').color), rgb(getComputedStyle(i).backgroundColor)]; })()")
        lum = lambda c: sum(w * (v / 255 / 12.92 if v / 255 <= 0.03928 else ((v / 255 + 0.055) / 1.055) ** 2.4) for w, v in zip((0.2126, 0.7152, 0.0722), c))
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.work(cdp, width)
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-close')", sid)))
                    for _ in range(2):
                        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
                        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "/", "code": "Slash", "windowsVirtualKeyCode": 191}, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .sn-in')", sid)))
                    ink, ground = cdp.js(probe, sid)
                    hi, lo = max(lum(ink), lum(ground)), min(lum(ink), lum(ground))
                    self.assertGreaterEqual((hi + 0.05) / (lo + 0.05), 4.5, f"placeholder {ink} on {ground}")
                    self.assertEqual(ink, cdp.js("(() => { const d = document.createElement('i'); d.style.color = 'var(--text-muted)'; document.body.append(d); const c = getComputedStyle(d).color; d.remove(); return (c.match(/[\\d.]+/g) || []).map(Number).slice(0, 3); })()", sid), "it is the muted text token")

    def test_the_words_box_is_a_foot_band_pinned_to_the_bottom_while_the_body_scrolls(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.work(cdp, width, height=560)                      # a short window: the peek's body is taller than the peek
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-close')", sid)))
                for _ in range(2):
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "/", "code": "Slash", "windowsVirtualKeyCode": 191}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .wordsbox')", sid)), "two slashes open the box")
                geo = "(() => { const p = document.querySelector('#peek'), w = p.querySelector('.wordsbox'), a = p.getBoundingClientRect(), b = w.getBoundingClientRect(), c = getComputedStyle(w); return { peekB: a.bottom, peekL: a.left, peekR: a.left + p.clientLeft + p.clientWidth, boxB: b.bottom, boxL: b.left, boxR: b.right, scroll: p.scrollHeight - p.clientHeight, top: p.scrollTop, line: c.borderTopWidth, radius: c.borderTopLeftRadius, shadow: c.boxShadow }; })()"
                cdp.js("document.querySelector('#peek').scrollTop = 0", sid)
                g = cdp.js(geo, sid)
                self.assertGreater(g["scroll"], 40, "the body is taller than the peek, so there is something to scroll: " + str(g))
                self.assertAlmostEqual(g["peekB"] - g["boxB"], 32, delta=1.5, msg="pinned 32px (the peek padding plus var(--space-2)) above the peek's bottom edge at the top of the scroll: " + str(g))
                self.assertAlmostEqual(g["boxL"], g["peekL"] + 1, delta=1.5, msg="the band spans the peek (its left edge is the peek's border): " + str(g))
                self.assertAlmostEqual(g["boxR"], g["peekR"], delta=1.5, msg="and reaches its right edge (the scrollbar's inner side): " + str(g))
                self.assertEqual((g["line"], g["radius"], g["shadow"]), ("1px", "0px", "none"), "a hairline above, no rounding, no floating shadow: " + str(g))
                inset = cdp.js("(() => { const p = document.querySelector('#peek'), w = p.querySelector('.wordsbox'), t = p.querySelector('.pk-title, .pk-title-in, h2, h3'), c = getComputedStyle(w), ta = w.querySelector('textarea, input, [contenteditable]'); return { box: w.getBoundingClientRect().left + parseFloat(c.paddingLeft), boxR: w.getBoundingClientRect().right - parseFloat(c.paddingRight), title: t ? t.getBoundingClientRect().left : null, ta: ta ? ta.getBoundingClientRect().left : null, pl: c.paddingLeft, pr: c.paddingRight }; })()", sid)
                self.assertIsNotNone(inset["title"], "the peek has a title to line up with: " + str(inset))
                self.assertAlmostEqual(inset["box"], inset["title"], delta=4, msg="the band's own padding keeps its words in line with the peek's title, not 20px further in: " + str(inset))
                self.assertEqual(inset["pl"], inset["pr"], "the same padding on both sides: " + str(inset))
                cdp.js("document.querySelector('#peek').scrollTop = 10000", sid)
                h = cdp.js(geo, sid)
                self.assertGreater(h["top"], 0, "the body scrolled")
                self.assertAlmostEqual(h["peekB"] - h["boxB"], 32, delta=1.5, msg="still 32px above the bottom edge after the scroll: " + str(h))


class SneakFlat(Peeks):
    """Row 1077: the sneak peek (the words box, .sn-* rules in shell.css and edit.css) is flat: no box round it and no shadow on its parts."""
    BOXLESS = (".sn-head", ".sn-list", ".sn-list li", ".sn-msg", ".sn-confirm", ".sn-foot", ".sn-acts", ".sn-chips")

    def test_no_sneak_rule_gives_a_part_a_shadow_and_the_box_rules_are_the_flat_band(self):
        import re
        css = (ROOT / "src" / "clark" / "page" / "shell.css").read_text(encoding="utf-8") + (SRC / "edit" / "edit.css").read_text(encoding="utf-8")
        rules = [(m.group(1).strip(), m.group(2)) for m in re.finditer(r"(?m)^\s*([^{}/@\n][^{}\n]*)\{([^{}]*)\}", css)]
        sneak = [(sel, body) for sel, body in rules if re.search(r"\.sn-[a-z]+", sel)]
        self.assertTrue(len(sneak) >= 8, "the sneak rules are found")
        for sel, body in sneak:
            self.assertNotIn("box-shadow", body.replace("box-shadow: none", ""), f"{sel}: no shadow on a sneak part")
        flat = [body for sel, body in rules if sel == ".peek .wordsbox"]
        self.assertEqual(len(flat), 1, "the peek's words box has one flat rule")
        for need in ("border: 0", "border-radius: 0", "box-shadow: none"):
            self.assertIn(need, flat[0], f"the words box in the peek: {need}")

    def test_the_open_sneak_peek_has_no_box_round_it_and_its_parts_are_flat(self):
        probe = ("(sels) => { const o = {}; for (const s of sels) { const e = document.querySelector('#peek ' + s); if (!e) continue; const c = getComputedStyle(e);"
                 " o[s] = [c.boxShadow, c.borderRadius, c.borderLeftWidth, c.borderRightWidth, c.borderBottomWidth]; } return o; }")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = Flat.work(self, cdp, width)
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-close')", sid)))
                for _ in range(2):
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "/", "code": "Slash", "text": "/", "windowsVirtualKeyCode": 191}, sid)
                    cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", "key": "/", "code": "Slash", "windowsVirtualKeyCode": 191}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .wordsbox')", sid)), "two slashes open the box")
                got = cdp.js(f"({probe})({json.dumps(['.wordsbox', *self.BOXLESS])})", sid)
                self.assertIn(".wordsbox", got)
                for sel, (shadow, radius, left, right, bottom) in got.items():
                    self.assertEqual(shadow, "none", f"{sel}: no shadow {got}")
                    self.assertEqual(radius, "0px", f"{sel}: square, no rounded box {got}")
                    self.assertEqual((left, right, bottom), ("0px", "0px", "0px"), f"{sel}: no side or bottom line {got}")


class ClientPeeksAlike(Peeks):
    """Row 1077: a client's work item peek and a client's milestone peek (the Dashboard in View) have one look: the same padding, header and tiles."""
    LOOK = """(() => {
      const css = (e, ks) => { const c = getComputedStyle(e); return ks.map(k => c[k]); };
      const pk = document.querySelector('#peek'), bar = pk.querySelector('.pk-bar'), title = pk.querySelector('.pk-title');
      const cell = pk.querySelector('.pk-fields > [data-row]') || pk.querySelector('.pk-fields > *');
      return { peek: css(pk, ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'backgroundColor', 'width']),
               bar: css(bar, ['paddingBottom', 'borderBottomWidth', 'height']),
               title: css(title, ['fontSize', 'fontWeight', 'lineHeight', 'marginTop', 'marginBottom', 'color']),
               tile: css(cell, ['paddingTop', 'paddingLeft', 'borderRadius', 'backgroundColor', 'boxShadow']) };
    })()"""

    def look_of(self, cdp, width, ref, kind):
        sid = self.dashboard_in_view(cdp, width, self.store, self.code)
        self.open_peek(cdp, sid, ref, kind)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').getAnimations({subtree: true}).every(a => a.playState !== 'running')", sid)), "the slide-in has ended")
        return cdp.js(self.LOOK, sid)

    def test_the_client_work_item_peek_and_the_client_milestone_peek_look_alike(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                with chrome() as cdp:
                    item = self.look_of(cdp, width, ACTION, "item")
                with chrome() as cdp:
                    milestone = self.look_of(cdp, width, MILESTONE, "milestone")
                for part in ("peek", "bar", "title", "tile"):
                    self.assertEqual(item[part], milestone[part], f"{part}: the milestone peek looks like the work item peek (item {item[part]}, milestone {milestone[part]})")


if __name__ == "__main__":
    unittest.main()
