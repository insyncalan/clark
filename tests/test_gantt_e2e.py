"""Row 926: the Gantt, end to end, in a real browser against the real server, the real store and the real Publish (the pieces were built
separately: the data layer, the chart, the table, the page, the tab, the Settings card, the publish gate; this is the one test that makes them
work together). Fictional data only (the PUB plant).

The flow, with the mouse and the keys: Settings > Gantt, tick "Show the Gantt to me" (the tab appears); on the Gantt page in Edit, add lines
below, edit a cell, drag a bar, press the eye; Chart and Table keep the mode; View shows only the lines with the eye on; Cmd+Z undoes through
the server's history; a reload keeps everything; the tab is renamed from the tab; a refusal is a toast in plain words; then tick "Show the Gantt
to the client", Publish, and open the published file: only the eye-on lines, the hidden columns gone, the tab there; untick, publish again: no
tab; and with no eye-on line the tab is absent.

Run: python3 dev/run_tests.py test_gantt_e2e
Set CLARK_E2E_SHOTS=<folder> to also save a screenshot of every step at 1400 and 900, light and dark. Chrome is required: this test fails,
never skips, without it.
"""
import json
import os
import re
import sqlite3
import time
import unittest
from pathlib import Path

import _paths  # noqa: F401  (puts src/ on the path)
from test_publish_route import Rig
from test_server import chrome, wait

SHOTS = os.environ.get("CLARK_E2E_SHOTS", "")
CODE = "PUB"
CMD = 4          # the Meta modifier of Input.dispatchKeyEvent


class Browser:
    """The harness's Chrome, with a real mouse and real keys."""

    def __init__(self, test, cdp, port):
        self.t, self.cdp, self.port, self.n = test, cdp, port, 0
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Page.enable", {}, self.sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, self.sid)
        self.width(1400)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": "try { localStorage.setItem('clark.section-style', 'slim'); } catch (e) {}"}, self.sid)

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def width(self, w, h=900):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, self.sid)

    def scheme(self, s):
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": s}]}, self.sid)

    def until(self, expr, what, seconds=12):
        self.t.assertTrue(wait(lambda: self.js(f"!!({expr})"), seconds), what + " | the toast says: " + str(self.text(".toasts")))

    def visit(self, url, ready="document.documentElement.dataset.ready === '1'"):
        self.cdp.call("Page.navigate", {"url": "about:blank"}, self.sid)      # so that the same address is a real reload
        self.cdp.call("Page.navigate", {"url": url}, self.sid)
        self.until(ready, "the page is ready: " + url)
        time.sleep(0.6)
        self.js("(function(){var b=[].find.call(document.querySelectorAll('button'),function(x){return x.textContent.trim()==='Not now'});if(b)b.click()})()")

    def where(self, sel):
        got = self.js(f"(function(){{var e=document.querySelector({json.dumps(sel)});if(!e)return null;e.scrollIntoView({{block:'center',inline:'center'}});"
                      "var b=e.getBoundingClientRect();return [b.x+b.width/2,b.y+b.height/2,b.width,b.height]})()")
        self.t.assertIsNotNone(got, f"{sel} is on the page")
        return got

    def mouse(self, kind, x, y, buttons=0):
        self.cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left" if buttons or kind == "mouseReleased" else "none",
                                                    "buttons": buttons, "clickCount": 1 if kind != "mouseMoved" else 0}, self.sid)

    def click(self, sel, dx=0, dy=0):
        x, y, *_ = self.where(sel)
        for kind, b in (("mouseMoved", 0), ("mousePressed", 1), ("mouseReleased", 0)):
            self.mouse(kind, x + dx, y + dy, b)
        time.sleep(0.25)

    def double_click(self, sel):
        x, y, *_ = self.where(sel)
        self.mouse("mouseMoved", x, y)
        for n in (1, 2):
            for kind, b in (("mousePressed", 1), ("mouseReleased", 0)):
                self.cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "buttons": b, "clickCount": n}, self.sid)
        time.sleep(0.3)

    def drag(self, sel, dx):
        x, y, w, _h = self.where(sel)
        x = x - w / 2 + 12            # a point well inside the bar's body, off its resize handle
        self.mouse("mouseMoved", x, y)
        self.mouse("mousePressed", x, y, 1)
        for i in range(1, 11):
            self.mouse("mouseMoved", x + dx * i / 10, y, 1)
        self.mouse("mouseReleased", x + dx, y)
        time.sleep(0.4)

    def key(self, key, mods=0, code=None, text=""):
        for kind in ("rawKeyDown" if mods else "keyDown", "keyUp"):
            self.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code or key, "modifiers": mods, "windowsVirtualKeyCode": {"Enter": 13, "Tab": 9, "Escape": 27}.get(key, ord(key.upper()) if len(key) == 1 else 0),
                                                      "text": text if kind != "keyUp" and not mods else ""}, self.sid)
        time.sleep(0.25)

    def type(self, text):
        self.cdp.call("Input.insertText", {"text": text}, self.sid)

    def fill(self, sel, text):
        """Click into a box, select what is in it and type over it."""
        self.click(sel)
        self.js(f"document.querySelector({json.dumps(sel)}).select()")
        self.type(text)

    def text(self, sel):
        return self.js(f"(function(){{var e=document.querySelector({json.dumps(sel)});return e?e.innerText.replace(/\\s+/g,' ').trim():null}})()")

    def snap(self, name):
        """A screenshot of this step at 1400 and 900, light and dark, when CLARK_E2E_SHOTS is set."""
        if not SHOTS:
            return
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        import base64
        for w in (1400, 900):
            self.width(w)
            for scheme in ("light", "dark"):
                self.scheme(scheme)
                time.sleep(0.35)
                data = self.cdp.call("Page.captureScreenshot", {"format": "png"}, self.sid)["data"]
                (Path(SHOTS) / f"{self.n:02d}-{name}-{scheme}-{w}.png").write_bytes(base64.b64decode(data))
        self.n += 1
        self.width(1400)
        self.scheme("light")
        time.sleep(0.2)


class E2E(unittest.TestCase):
    def setUp(self):
        self.rig = Rig(self)
        self.base = f"http://127.0.0.1:{self.rig.httpd.server_port}/"
        self.published = 0
        status, body = self.rig.call("POST", "/api/profile", {"name": "Sam Carter", "email": "sam@example.com"})       # Publish needs a name
        self.assertEqual((status, body["ok"]), (200, True), body)

    # ── what the server holds ────────────────────────────────────────────────

    def db(self, sql, *args):
        con = sqlite3.connect(self.rig.db)
        con.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in con.execute(sql, args)]
        finally:
            con.close()

    def lines(self):
        return self.db("SELECT * FROM gantt_lines WHERE project = ? ORDER BY sort_order, id", CODE)

    def line(self, name):
        got = [r for r in self.lines() if r["name"] == name]
        self.assertEqual(len(got), 1, f"one line called {name}: {[r['name'] for r in self.lines()]}")
        return got[0]

    def names(self):
        return [r["name"] for r in self.lines()]

    def project(self):
        return self.db("SELECT * FROM projects WHERE code = ?", CODE)[0]

    def send(self, **req):
        status, body = self.rig.call("POST", "/api/change", {"project": CODE, **req})
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body

    def publish(self, br):
        """Publish through the dialog (the Save window is the rig's), and the path of the file."""
        self.published += 1
        self.rig.save_to = self.rig.local / f"published-{self.published}.html"
        br.js("document.querySelector('#profile-btn').click()")
        br.until("[].find.call(document.querySelectorAll('#profile-menu [role=menuitem]'), function(e){return /^Publish/.test(e.textContent.trim())})", "the menu has Publish")
        br.js("[].find.call(document.querySelectorAll('#profile-menu [role=menuitem]'), function(e){return /^Publish/.test(e.textContent.trim())}).click()")
        br.until("document.querySelector('#publish-dialog[open]')", "the dialog opened")
        br.snap("publish-dialog")
        br.click("[data-go]")
        br.until("/Published/.test(document.querySelector('#pub-msg').innerText)", "it says Published", 30)
        self.assertTrue(self.rig.save_to.exists(), "the file was saved")
        br.js("(document.querySelector('[data-cancel],[data-close],#pub-done')||{click(){}}).click()")
        return self.rig.save_to

    def tabs(self, br):
        return br.js("[].map.call(document.querySelectorAll('.tab'), function(t){return t.textContent.trim()})")

    # ── the flow ─────────────────────────────────────────────────────────────

    def test_the_gantt_from_settings_to_the_published_file(self):
        with chrome() as cdp:
            br = Browser(self, cdp, self.rig.httpd.server_port)
            self.settings_and_the_tab(br)
            self.add_edit_drag_eye(br)
            self.chart_table_view(br)
            self.undo_and_reload(br)
            self.rename_the_tab_and_the_template(br)
            self.refusal_is_a_toast(br)
            self.published_file(br)

    def settings_and_the_tab(self, br):
        br.visit(self.base + f"#settings&p={CODE}", "document.querySelector('#gantt-setting, [data-settings-menu], .setting')")
        self.assertNotIn("Gantt", self.tabs(br), "the tab is off to begin with")
        br.until("[].some.call(document.querySelectorAll('button, a, li'), function(b){return b.textContent.trim()==='Gantt'})", "Settings lists Gantt")
        br.js("[].find.call(document.querySelectorAll('button, a'), function(b){return b.textContent.trim()==='Gantt'}).click()")
        br.until("document.querySelector('#gantt-editor')", "the Gantt card")
        self.assertIn("Show the Gantt to me", br.text("#gantt-setting"))
        self.assertEqual(br.text("#gantt-setting h2"), "Gantt")
        br.snap("settings-gantt-card")
        br.click("#gantt-editor")
        br.until("[].some.call(document.querySelectorAll('.tab'), function(t){return t.textContent.trim()==='Gantt'})", "the tab appears")
        self.assertEqual(self.project()["show_gantt_editor"], 1)
        self.assertIn("The Gantt tab is on for you.", br.text(".toasts") or "")
        br.snap("tab-on")
        br.click(".tab[data-view=gantt]")
        br.until("document.querySelector('#gantt-page')", "the Gantt page")
        self.assertEqual(br.text("[data-g-none]"), "No lines to show.", "no line yet")
        br.snap("gantt-empty-view")

    def add_edit_drag_eye(self, br):
        br.click("[data-gp-mode=edit]")
        br.until("document.querySelector('#gantt-page').dataset.mode === 'edit'", "Edit")
        br.until("document.querySelector('[data-gp-first]')", "an empty plan in Edit offers the first line")
        br.snap("gantt-empty-edit")
        br.click("[data-gp-first]")
        br.until("document.querySelector('[data-g-row]')", "the first line is drawn")
        first = self.lines()
        self.assertEqual([(r["type"], r["name"], r["show"]) for r in first], [("phase", "New phase", 0)])
        self.assertTrue(re.fullmatch(r"PUB-GNT-001", first[0]["id"]), "stored as CODE-GNT-001")
        self.assertEqual(br.js("document.querySelector('[data-g-row]').dataset.gNo + '|' + document.querySelector('[data-g-row] .gt-id').innerText"), "1|1", "the page shows GNT ids and outline numbers")
        # rename the phase, then add a task below it (the + menu)
        br.fill("[data-g-edit$=':name']", "Discovery")
        br.key("Enter")
        self.assertTrue(wait(lambda: self.names() == ["Discovery"]), self.names())
        br.click("[data-g-add]")
        br.until("document.querySelector('[data-g-addmenu]')", "the add menu")
        br.snap("gantt-add-menu")
        br.click("[data-g-addtype=task]")
        br.until("document.querySelectorAll('[data-g-row]').length === 2", "the task is drawn")
        rows = self.lines()
        self.assertEqual([(r["type"], r["name"]) for r in rows], [("phase", "Discovery"), ("task", "New task")])
        self.assertEqual(rows[1]["parent"], "PUB-GNT-001", "under the phase it was added below")
        self.assertEqual(rows[1]["id"], "PUB-GNT-002")
        # add a milestone below the task
        br.click("[data-g-add='GNT-002']")
        br.click("[data-g-addtype=milestone]")
        br.until("document.querySelectorAll('[data-g-row]').length === 3", "the milestone is drawn")
        self.assertEqual([r["type"] for r in self.lines()], ["phase", "task", "milestone"])
        # edit cells: the task's name, then its dates in the detail box
        br.fill("[data-g-edit='GNT-002:name']", "Scan paper files")
        br.key("Enter")
        self.assertTrue(wait(lambda: "Scan paper files" in self.names()), self.names())
        br.double_click("[data-g-bar='GNT-002']")
        br.until("document.querySelector('[data-g-box]')", "the edit box opens on a double click")
        br.fill("[data-g-bs]", "05-10-2026")
        br.fill("[data-g-be]", "06-11-2026")
        br.fill("[data-g-bp]", "40")
        br.snap("gantt-edit-box")
        br.click("[data-g-bsave]")
        self.assertTrue(wait(lambda: self.line("Scan paper files")["end"] == "2026-11-06"), self.lines())
        task = self.line("Scan paper files")
        self.assertEqual((task["start"], task["end"], task["pct"]), ("2026-10-05", "2026-11-06", 40), "dates stored as YYYY-MM-DD, done as a whole number")
        self.assertIn("changed", br.text(".toasts") or "")
        # drag the task's bar a week to the right
        was = (task["start"], task["end"])
        br.drag("[data-g-bar='GNT-002']", 60)
        self.assertTrue(wait(lambda: (self.line("Scan paper files")["start"], self.line("Scan paper files")["end"]) != was), "the bar moved")
        moved = self.line("Scan paper files")
        self.assertGreater(moved["start"], was[0])
        self.assertEqual(self.db("SELECT count(*) n FROM gantt_lines WHERE project = ?", CODE)[0]["n"], 3, "a drag changes no other line")
        br.snap("gantt-edit-after-drag")
        # the eye: the phase and the task go on the dashboard, the milestone stays off
        br.click("[data-g-eye='GNT-001']")
        br.click("[data-g-eye='GNT-002']")
        self.assertTrue(wait(lambda: [r["show"] for r in self.lines()] == [1, 1, 0]), str([(r["id"], r["type"], r["name"], r["show"]) for r in self.lines()]) + br.text(".toasts"))
        br.snap("gantt-edit-eyes")

    def chart_table_view(self, br):
        # the mode is kept when the layout changes
        br.click("[data-gp-layout=table]")
        br.until("document.querySelector('#gantt-page').dataset.gpShown === 'table'", "the table")
        self.assertEqual(br.js("document.querySelector('#gantt-page').dataset.mode"), "edit", "Edit is kept")
        br.until("document.querySelector('.gt-scroll td[data-r]')", "the table has rows")
        br.snap("gantt-table-edit")
        # edit a cell in the table: select it, type over it (Enter commits)
        br.double_click(".gt-scroll td[data-r='2'][data-c='1']")
        br.until("document.querySelector('.gt-scroll td.gt-ed input')", "the cell opens for typing on a double click")
        br.js("document.querySelector('.gt-scroll td.gt-ed input').select()")
        br.type("Handover")
        br.key("Enter")
        self.assertTrue(wait(lambda: "Handover" in self.names()), self.names())
        self.assertEqual(self.line("Handover")["type"], "milestone")
        # Import from Excel opens the editor's own two-step box (the one Settings > Data opens), then Cancel puts the page back
        br.click("[data-gp-import]")
        br.until("document.querySelector('#import-box')", "Import from Excel opens the editor's own import box")
        br.js("document.querySelector('#import-box').closest('dialog, [role=dialog], div').querySelector('.btn.quiet:not(.tpl-get)').click()")
        br.until("!document.querySelector('#import-box')", "Cancel closes the import box")
        br.click("[data-gp-layout=chart]")
        br.until("document.querySelector('#gantt-page').dataset.gpShown === 'chart'", "the chart")
        self.assertEqual(br.js("document.querySelector('#gantt-page').dataset.mode"), "edit")
        self.assertEqual(br.js("document.querySelectorAll('[data-g-row]').length"), 3, "Edit draws every line")
        # View: only the lines with the eye on
        br.click("[data-gp-mode=view]")
        br.until("document.querySelector('#gantt-page').dataset.mode === 'view'", "View")
        self.assertEqual(br.js("document.querySelectorAll('[data-g-row]').length"), 2)
        self.assertEqual(br.js("[].map.call(document.querySelectorAll('[data-g-row] .gt-nm'), function(e){return e.textContent}).join('|')"), "Discovery|Scan paper files")
        self.assertEqual(br.js("document.querySelectorAll('[data-g-eye], [data-g-add]').length"), 0, "View has no editing controls")
        br.snap("gantt-view-chart")
        br.click("[data-gp-layout=table]")
        br.until("document.querySelector('#gantt-page').dataset.gpShown === 'table'", "the table in View")
        self.assertEqual(br.js("document.querySelectorAll('.gt-scroll td[data-c=\"1\"]').length"), 2, "the View table has the two lines with the eye on")
        br.snap("gantt-view-table")
        br.click("[data-gp-layout=chart]")
        br.click("[data-gp-mode=edit]")
        br.until("document.querySelector('#gantt-page').dataset.mode === 'edit'", "Edit again")

    def undo_and_reload(self, br):
        before = self.line("Scan paper files")["end"]
        # a change, then Cmd+Z: the server's own history puts it back
        br.fill("[data-g-edit='GNT-002:name']", "Scan the paper files")
        br.key("Enter")
        self.assertTrue(wait(lambda: "Scan the paper files" in self.names()), self.names())
        br.js("document.activeElement && document.activeElement.blur()")
        br.key("z", CMD, "KeyZ")
        self.assertTrue(wait(lambda: "Scan paper files" in self.names()), f"Cmd+Z undid the rename: {self.names()}")
        self.assertEqual(self.line("Scan paper files")["end"], before)
        # the toast's own Undo button: add a line, then press Undo on the toast
        count = len(self.lines())
        br.click("[data-g-add='GNT-001']")
        br.click("[data-g-addtype=task]")
        self.assertTrue(wait(lambda: len(self.lines()) == count + 1), "a line was added")
        br.until("document.querySelector('.toasts button')", "the toast offers Undo")
        br.snap("toast-with-undo")
        br.js("[].find.call(document.querySelectorAll('.toasts button'), function(b){return /Undo/.test(b.textContent)}).click()")
        self.assertTrue(wait(lambda: len(self.lines()) == count), "the toast's Undo removed it")
        # a reload keeps everything
        shown = br.js("[].map.call(document.querySelectorAll('[data-g-row] .gt-nm'), function(e){return e.value||e.textContent}).join('|')")
        br.visit(self.base + f"#gantt&p={CODE}")
        br.until("document.querySelector('[data-g-row]')", "the Gantt page after a reload")
        self.assertEqual(br.js("document.querySelector('#gantt-page').dataset.mode"), "view", "a reload is View")
        br.click("[data-gp-mode=edit]")
        br.until("document.querySelectorAll('[data-g-row]').length === 3", "all three lines are back")
        again = br.js("[].map.call(document.querySelectorAll('[data-g-row] .gt-nm'), function(e){return e.value||e.textContent}).join('|')")
        self.assertEqual(again, shown)
        self.assertEqual([r["show"] for r in self.lines()], [1, 1, 0])
        br.snap("gantt-after-reload")

    def rename_the_tab_and_the_template(self, br):
        br.click(".tab[data-view=gantt]")          # clicking the open tab's name in Edit renames it
        br.until("document.querySelector('.tab[data-view=gantt] input')", "the tab's name is a box")
        br.js("document.querySelector('.tab[data-view=gantt] input').select()")
        br.type("Plan")
        br.key("Enter")
        self.assertTrue(wait(lambda: self.project()["gantt_tab_name"] == "Plan"), self.project())
        self.assertIn("Plan", self.tabs(br))
        self.assertNotIn("Gantt", self.tabs(br))
        br.snap("tab-renamed")
        # the Dashboard's Gantt section template is listed, read, and placeable (row 926)
        br.click(".tab[data-view=dashboard]")
        br.until("document.querySelector('#report [data-id]')", "the Dashboard")
        br.js("document.dispatchEvent(new CustomEvent('clark:add-section', {detail: {after: document.querySelector('#report [data-id]').dataset.id, opener: document.activeElement}, cancelable: true, bubbles: true}))")
        br.until("document.querySelector('[data-template=gantt]')", "the Add a section box lists the Gantt template")
        card = br.text("[data-template=gantt]")
        self.assertIn("The plan as bars on a timeline, from your Gantt lines. Only lines put on the dashboard show.", card)
        self.assertNotIn("Coming with a later release.", card)
        br.js("document.querySelector('[data-template=gantt] input, input[value=gantt]').click()")
        br.until("!document.querySelector('button[data-place]').disabled", "the Gantt can be placed")
        br.snap("section-template-placeable")
        br.key("Escape")
        br.click(".tab[data-view=gantt]")
        br.until("document.querySelector('#gantt-page')", "back on the Gantt page")

    def refusal_is_a_toast(self, br):
        # the server refuses a change the page cannot judge (a phase with lines under it made a task): plain words in a toast, nothing changes
        br.click("[data-gp-layout=table]")
        br.until("document.querySelector('.gt-scroll td[data-r=\"0\"][data-c=\"2\"]')", "the table")
        was = self.lines()
        br.click(".gt-scroll td[data-r='0'][data-c='2']")
        br.key("t", text="t")
        br.until("document.querySelector('.gt-scroll td.gt-ed select')", "the Type cell opens on a typed letter")
        br.key("Enter")
        br.until("/A phase with lines under it stays a phase/.test(document.querySelector('.toasts').innerText)", "the refusal is a toast, in the server's plain words")
        self.assertEqual(self.lines(), was, "a refused change writes nothing")
        br.until("document.querySelector('.gt-scroll td[data-r=\"0\"][data-c=\"2\"]').innerText.trim() === 'Phase'", "the table shows the saved type again")
        br.snap("refusal-toast")
        br.click("[data-gp-layout=chart]")

    def published_file(self, br):
        # the client switch on, then Publish: the file carries the Gantt
        self.send(kind="projects", op="update", changes={"gantt_hidden_columns": "show,note,budget,effort,baseline_start,baseline_end,owner"})
        br.visit(self.base + f"#settings&p={CODE}", "document.querySelector('.setting, #gantt-setting')")
        br.js("[].find.call(document.querySelectorAll('button, a'), function(b){return b.textContent.trim()==='Gantt'}).click()")
        br.until("document.querySelector('#gantt-client')", "the client tick")
        br.click("#gantt-client")
        self.assertTrue(wait(lambda: self.project()["show_gantt_client"] == 1), "ticked")
        br.until("/client's report/.test(document.body.innerText)", "its toast")
        br.snap("settings-client-tick")
        first = self.publish(br)
        text = first.read_text(encoding="utf-8")
        self.assertNotIn("PUB-GNT-003", text, "the line with the eye off is not in the file")
        self.assertNotIn("Handover", text)
        br.visit("file://" + str(first) + f"#gantt")
        br.until("document.querySelector('#gantt-page')", "the published Gantt page")
        self.assertIn("Plan", self.tabs(br), "the Gantt tab is in the file, under its name")
        self.assertEqual(br.js("document.querySelector('#gantt-page').dataset.mode"), "view")
        self.assertEqual(br.js("document.querySelectorAll('[data-g-row]').length"), 2)
        self.assertEqual(br.js("document.querySelectorAll('[data-gp-mode], [data-g-eye], [data-g-add], .modes').length"), 0, "a published file is View only")
        br.snap("published-chart")
        br.click("[data-gp-layout=table]")
        br.until("document.querySelector('#gantt-page').dataset.gpShown === 'table'", "the table in the file")
        head = br.js("[].map.call(document.querySelectorAll('.gt-scroll thead th, .gt-scroll [role=columnheader]'), function(h){return h.innerText.replace(/\\s+/g,' ').trim()}).join('|')")
        self.assertNotIn("Owner", head, "a hidden column is not in the file")
        self.assertNotIn("Notes", head)
        self.assertIn("Start", head)
        br.snap("published-table")
        # untick: the next file has no Gantt tab
        br.visit(self.base + f"#settings&p={CODE}", "document.querySelector('.setting, #gantt-setting')")
        br.js("[].find.call(document.querySelectorAll('button, a'), function(b){return b.textContent.trim()==='Gantt'}).click()")
        br.until("document.querySelector('#gantt-client')", "the client tick")
        br.click("#gantt-client")
        self.assertTrue(wait(lambda: self.project()["show_gantt_client"] == 0), "unticked")
        second = self.publish(br)
        br.visit("file://" + str(second) + "#dashboard")
        br.until("document.querySelector('.tab')", "the second file")
        self.assertNotIn("Plan", self.tabs(br))
        self.assertNotIn("PUB-GNT-001", second.read_text(encoding="utf-8"), "no Gantt line is in a file made with the client switch off")
        br.snap("published-no-tab")
        # ticked again but no line has its eye on: no tab either
        self.send(kind="projects", op="update", changes={"show_gantt_client": 1})
        for r in self.lines():
            if r["show"]:
                self.send(kind="gantt_lines", op="update", id=r["id"], changes={"show": 0})
        br.visit(self.base + f"#dashboard&p={CODE}")
        third = self.publish(br)
        br.visit("file://" + str(third) + "#dashboard")
        br.until("document.querySelector('.tab')", "the third file")
        self.assertNotIn("Plan", self.tabs(br), "no line with its eye on, no tab")
        # one line back on, and every column the client may be denied hidden: the file still draws the chart with its dates (Type, Start, End and Done are
        # never hidden, and the data layer refuses them), never "No lines to show."
        self.send(kind="gantt_lines", op="update", id="PUB-GNT-001", changes={"show": 1})
        status, body = self.rig.call("POST", "/api/change", {"project": CODE, "kind": "projects", "op": "update", "changes": {"gantt_hidden_columns": "start,end,pct"}})
        self.assertEqual(status, 400, "the data layer refuses the dates as hidden columns")
        self.send(kind="projects", op="update", changes={"gantt_hidden_columns": "show,note,budget,effort,baseline_start,baseline_end,owner"})
        br.visit(self.base + f"#dashboard&p={CODE}")
        fourth = self.publish(br)
        br.visit("file://" + str(fourth) + "#gantt")
        br.until("document.querySelector('#gantt-page')", "the fourth file's Gantt page")
        self.assertIn("Plan", self.tabs(br))
        self.assertEqual(br.js("document.querySelectorAll('[data-g-none]').length"), 0, "a file with lines never says there are none")
        self.assertEqual(br.js("document.querySelector('#gantt-page').dataset.gpShown"), "chart", "the dates are always in the file, so the bars are drawn")
        head = br.js("[].map.call(document.querySelectorAll('.gt-lhead .gt-h'), function(h){return h.innerText.trim()}).join('|')")
        self.assertIn("Start", head)
        self.assertIn("Done", head)
        br.snap("published-hidden-columns")


if __name__ == "__main__":
    unittest.main()
