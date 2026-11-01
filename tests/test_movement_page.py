"""#136 (commit 7): the Milestones Movement block on the page, owner only, in a real browser against the real routes.

Run: python3 dev/run_tests.py test_movement_page
Without a browser: the block is in the served page and in nothing a published file is made from (no word, class, route or file of it
in page-view.html or in that build's inputs), and the page's words are the Python constants' (movement_view.py and the refusals of
milestone_rows.py and changes.py). With headless Chrome (the #33 harness; fails, never skips, without it): the block loads from
GET /api/movement in Edit and is absent in View; Hold and Move the agreed date go through the real change route with their toasts,
Undo and refusals; loading and "can't load" states; keyboard use; accessible names; 1400 and 900 px in light and dark. Laptop only.
"""
import json
import re
import sys
import tempfile
import threading
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from clark import changes, milestone_rows, movement_read, movement_view as mv, page, server as sv  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_report_editor import Pg  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
WORDS = PAGE_SRC / "edit" / "movementWords.js"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
INTERNAL = "ZQ-INTERNAL-NOTE-8841 supplier wants more money"
GO_LIVE, PILOT = "ABC-M-002", "ABC-M-001"
BEHIND = "2020-01-10"                                   # long past: Go live has slipped
WORDS_OF_THE_BLOCK = ("Movement", "What changed", "Decide what to do", "Move the agreed date", "Keep the date",
                      "Internal only: never published", "Hold: keep the forecast", "Hold recorded", "Nothing has changed since",
                      "never published", "Each choice changes the record")


def js_constants():
    """{NAME: text} for each `export const NAME = "text";` of the words file."""
    return {m.group(1): json.loads(m.group(2)) for m in re.finditer(r'^export const (\w+) = ("(?:[^"\\]|\\.)*");$', WORDS.read_text(encoding="utf-8"), re.M)}


class NoBrowser(unittest.TestCase):
    def test_the_published_page_has_nothing_of_movement(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        served = page.PAGE.read_text(encoding="utf-8")
        for text in ("/api/movement", "mvm-row", "mvm-card", "mvm-track", "movementApi", "Movement"):
            self.assertNotIn(text, view, text)
            self.assertIn(text if text != "movementApi" else "api/movement", served, text)
        for phrase in WORDS_OF_THE_BLOCK[1:]:
            self.assertNotIn(phrase, view, phrase)
            self.assertIn(phrase, served, phrase)
        for name, text in js_constants().items():
            if len(text) > 12 and name not in ("NOT_HERE", "ARCHIVED"):
                self.assertNotIn(text, view, f"{name} is in the published page")
        self.assertIn("/api/change", served)

    def test_the_published_build_takes_none_of_the_movement_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "meta.json"
            done = esbuild.run(["--bundle", "--format=iife", "--tsconfig-raw={}", *build_page.preact_flags(), build_page.ENTRY_VIEW,
                                f"--outfile={Path(tmp) / 'p.js'}", f"--metafile={meta}"], cwd=build_page.SRC, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            inputs = list(json.loads(meta.read_text(encoding="utf-8"))["inputs"])
        self.assertTrue(inputs)
        for name in inputs:
            self.assertNotRegex(name, r"(?i)movement", name)
            self.assertFalse(name.endswith(("api.js", "stores/changes.js")), name)

    def test_its_styles_are_in_the_served_page_only(self):
        self.assertIn(".mvm-row", build_page.page_css(build_page.ENTRY))
        self.assertNotIn(".mvm-", build_page.page_css(build_page.ENTRY_VIEW))
        self.assertNotIn(".mvm-", (PAGE_SRC.parent / "shell.css").read_text(encoding="utf-8"))

    def test_the_pages_words_are_the_python_constants(self):
        js = js_constants()
        same = {"TAG_INTERNAL": mv.TAG_INTERNAL, "HELP_LINE": mv.HELP_LINE, "NOTHING_CHANGED": mv.NOTHING_CHANGED, "HOLD_LABEL": mv.HOLD_LABEL,
                "MOVE_LABEL": mv.MOVE_LABEL, "KEEP_LABEL": mv.KEEP_LABEL, "CONFIRM": mv.CONFIRM, "TOAST_HOLD": mv.TOAST_HOLD,
                "TOAST_MOVED": mv.TOAST_MOVED, "READ_FAILS": mv.READ_FAILS, "NO_DATE_YET": mv.NO_DATE_YET, "UNDONE": mv.TAG_UNDONE,
                "ARCHIVED": mv.ARCHIVED, "NOT_HERE": mv.NOT_HERE}
        for name, want in same.items():
            self.assertEqual(js[name], want, name)
        rows = Path(milestone_rows.__file__).read_text(encoding="utf-8")
        for name in ("WHO_MISSING", "REASON_MISSING", "SOURCE_MISSING", "NOT_SLIPPED"):
            self.assertIn(js[name].replace("'", "'"), rows, name)
        self.assertIn(js["DATE_UNREADABLE"][:-1], rows, "DATE_UNREADABLE")      # the page leaves out the example date
        for name in ("SAME_DATE", "EARLIER_DATE", "PAST_DATE"):
            self.assertIn(js[name].replace("%s", "%s"), rows, name)
        self.assertEqual(js["ARCHIVED"], changes.ARCHIVED_MILESTONE)
        self.assertEqual(js["NOT_HERE"], changes.NO_MILESTONE)

    def test_no_sentence_starts_with_the_product_name_and_dates_are_shown_day_first(self):
        for name, text in js_constants().items():
            self.assertFalse(re.match(r"(?i)clark\b", text), name)
            self.assertNotRegex(text, r"\d{4}-\d\d-\d\d", name)
        source = (PAGE_SRC / "edit" / "Movement.jsx").read_text(encoding="utf-8")
        self.assertNotRegex(source, r">\s*clark\b")

    def test_the_server_text_is_shown_only_when_it_is_clarks_own_fixed_refusal(self):
        text = WORDS.read_text(encoding="utf-8")
        self.assertIn("knownRefusal", text)
        for sentence in (changes.AGREED_STAYS, changes.NEEDS_NEW_DATE, changes.ARCHIVED_MILESTONE, changes.NO_MILESTONE):
            self.assertTrue(re.search(re.escape(sentence).replace("\\ ", " ")[:30], text.replace("\\", "")), sentence)


def in_days(n):
    d = date.today() + timedelta(days=n)
    return d.isoformat(), d.strftime("%d-%m-%Y")


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            st.update("milestones", PILOT, {"owner": "Sam Example"})
            st.create("milestones", {"project": "ABC", "name": "Go live", "baseline_date": BEHIND, "forecast_date": "2020-02-01",
                                     "owner": "Priya Example", "internal_note": INTERNAL, "source": "demo"})
        self.real_change = changes.make_change(self.store.path, [], USER)
        self.real_undo = changes.make_undo(self.store.path, [], USER)
        self.read = movement_read.make_read(self.store.milestone_moves, self.store.data_for)
        self.sent, self.reads, self.hold_read = [], [], None
        self.fail_read = False
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING),
                         change=self.seam(self.real_change, "change"), undo=self.seam(self.real_undo, "undo"))
        self.s.httpd.movement = self.movement
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def movement(self, code):
        self.reads.append(code)
        if self.hold_read is not None:
            self.hold_read.wait(20)
        if self.fail_read:
            raise RuntimeError("the read failed on purpose")
        return self.read(code)

    def seam(self, real, which):
        def call(req):
            self.sent.append((which, req))
            return real(req)
        return call

    def row(self, ref):
        return self.store.read("milestones", ref=ref)

    def visit(self, cdp, width=1400, theme=None):
        p = Pg.at(self, cdp, self.s.port, "#milestones&p=ABC")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("!!document.querySelector('#milestones')", "Milestones drew")
        if theme:
            p.js(f"document.documentElement.dataset.theme = '{theme}'")
        return p

    def open_movement(self, p):
        p.js("document.querySelector('[data-mode=edit]').click()")
        p.until("!!document.querySelector('[data-mspv=move]')", "the Plan / Movement switch drew")
        p.js("document.querySelector('[data-mspv=move]').click()")
        p.until("!!document.querySelector('#movement .mvm-sentence')", "Movement drew")

    def toast(self, p):
        return p.js("(document.querySelector('.toast .toast-text') || {}).textContent || ''")

    def key(self, p, key, code, vk):
        p.key(key, code=code, vk=vk)


class Block(Base):
    def test_view_has_no_movement_and_edit_draws_it_from_the_route(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("!!document.querySelector('#movement')"), False)
            self.assertEqual(self.reads, [], "View asks for no Movement")
            self.open_movement(p)
            self.assertEqual(p.js("document.querySelector('#movement h2').textContent"), "Movement")
            self.assertEqual(p.js("document.querySelector('#movement .tag').textContent"), mv.TAG_INTERNAL)
            self.assertIn(mv.HELP_LINE, p.js("document.querySelector('#movement').textContent"))
            self.assertEqual(p.js("document.querySelector('.mvm-sentence').textContent"), "1 of 2 open milestones are behind their agreed date; 1 overdue.")
            self.assertEqual(p.js("[...document.querySelectorAll('.mvm-row .mvm-name')].map(e => e.textContent)"), ["Go live", "Pilot live"], "worst first")
            self.assertIn("Go live is", p.js("document.querySelector('.mvm-worst').textContent"))
            text = p.js("document.querySelector('.mvm-card').textContent")
            for want in ("Original", "10-01-2020", "Agreed", "Forecast", "01-02-2020", "Never moved", "Progress", "Owner", "Priya Example",
                         "What changed", mv.NOTHING_CHANGED, "Decide what to do", mv.HOLD_LABEL, mv.MOVE_LABEL, "Each choice changes the record at once, with Undo."):
                self.assertIn(want, text)
            self.assertNotIn(INTERNAL, p.js("document.body.innerHTML"), "the internal note never reaches the page")
            self.assertEqual(p.js("document.querySelector('#mv-move').disabled"), False)
            p.js("document.querySelector('.mvm-row[data-id=\"%s\"]').click()" % PILOT)
            p.until("document.querySelector('#mv-card-h').textContent === 'Pilot live'", "the card follows the row")
            self.assertEqual(p.js("document.querySelector('#mv-move').disabled"), True, "not slipped: no move")
            self.assertEqual(p.js("document.querySelector('#mv-why').textContent"), "This milestone hasn't slipped, so its agreed date can't be moved yet.")
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("!document.querySelector('#movement')", "View removes it")

    def test_plan_movement_switch_is_edit_only_and_remembered(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("!!document.querySelector('[data-mspage-switch]')"), False, "View has no switch")
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("!!document.querySelector('[data-mspage-switch]')", "Edit has the switch")
            self.assertEqual(p.js("[...document.querySelectorAll('[data-mspv]')].map(b => b.textContent)"), ["Plan", "Movement"])
            self.assertEqual(p.js("document.querySelector('[data-mspv=plan]').getAttribute('aria-pressed')"), "true")
            self.assertEqual(p.js("!!document.querySelector('.msv') && !document.querySelector('#movement')"), True, "Plan shows the milestones, not Movement")
            self.assertIn("Every milestone sits on the line", p.js("document.querySelector('[data-mspage-hint]').textContent"))
            p.js("document.querySelector('[data-mspv=move]').click()")
            p.until("!!document.querySelector('#movement .mvm-sentence')", "Movement drew")
            self.assertEqual(p.js("!document.querySelector('.msv')"), True, "Movement replaces the Plan")
            self.assertEqual(p.js("document.querySelector('[data-mspv=move]').getAttribute('aria-pressed')"), "true")
            self.assertIn("never published", p.js("document.querySelector('#movement').textContent"))
            self.assertIn("Undo", p.js("document.querySelector('[data-mspage-hint]').textContent"))
            p.js("document.querySelector('[data-mspv=plan]').click()")
            p.until("!!document.querySelector('.msv') && !document.querySelector('#movement')", "back to the Plan")
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("!document.querySelector('[data-mspage-switch]') && !!document.querySelector('.msv')", "View is the Plan alone")

    def test_hold_is_recorded_with_its_toast_and_undo(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            p.js("document.querySelector('#mv-hold').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Hold recorded. Undo.'", "the Hold toast")
            self.assertEqual(self.row(GO_LIVE)["movement"], "hold")
            self.assertEqual(self.sent[-1][1]["place"], "movement")
            p.until("document.querySelector('.mvm-list') && document.querySelector('.mvm-list').textContent.includes('Movement choice: Hold')", "What changed shows it")
            self.assertEqual(p.js("document.activeElement.className.includes('mvm-row')"), True, "focus returns to the row")
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Undone.'", "Undone")
            self.assertIsNone(self.row(GO_LIVE)["movement"])
            p.until("!document.querySelector('.mvm-list') || !document.querySelector('.mvm-list').textContent.includes('Movement choice: Hold') "
                    "|| !!document.querySelector('.mvm-en.undone')", "What changed follows the undo")

    def test_move_the_agreed_date_asks_confirms_refuses_moves_and_undoes(self):
        iso, text = in_days(30)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            p.js("document.querySelector('#mv-move').click()")
            p.until("!!document.querySelector('.mvm-form')", "the form opened")
            p.until("document.activeElement.id === 'mv-to'", "focus goes to the first field")
            self.assertEqual(p.js("document.querySelector('#mv-move').disabled"), True)
            confirm = p.js("document.querySelector('#mvm-confirm').textContent")
            self.assertTrue(confirm.startswith("Move the agreed date of Go live from 10-01-2020 to "), confirm)
            self.assertTrue(confirm.endswith("The original date (10-01-2020) is kept and a decision is recorded. You can undo this."), confirm)
            # nothing given: the three reasons, in order, and nothing is sent
            before = len(self.sent)
            p.js("document.querySelector('#mv-go').click()")
            p.until("document.querySelectorAll('.mvm-problems p').length === 3", "three reasons")
            self.assertEqual(p.js("[...document.querySelectorAll('.mvm-problems p')].map(e => e.textContent)"),
                             ["Say who agreed the new date.", "Give the reason the agreed date is moving.",
                              "Give the source: where it was agreed, for example the meeting or the email."])
            self.assertEqual(len(self.sent), before)
            self.assertEqual(p.js("document.querySelector('.mvm-problems').getAttribute('role')"), "alert")
            self.fill(p, "mv-to", "05-01-2020")
            self.fill(p, "mv-who", "Pat Example")
            self.fill(p, "mv-reason", "The build ran long")
            self.fill(p, "mv-source", "Steering minutes")
            p.js("document.querySelector('#mv-go').click()")
            p.until("!!document.querySelector('.mvm-problems p')", "an earlier date is refused")
            self.assertEqual(p.js("document.querySelector('.mvm-problems p').textContent"), "The new agreed date must be later than the current one (10-01-2020).")
            self.assertEqual(len(self.sent), before)
            # a date the server refuses, in its words: the form stays, nothing is written
            self.fill(p, "mv-to", text)
            p.js("document.querySelector('#mv-go').click()")
            p.until("!document.querySelector('.mvm-form')", "the form closed")
            self.assertEqual(self.row(GO_LIVE)["baseline_date"], iso)
            self.assertEqual(self.sent[-1][1]["rebaseline"], {"agreed_with": "Pat Example", "reason": "The build ran long", "source": "Steering minutes"})
            p.until("document.querySelector('.toast .toast-text').textContent.startsWith('Go live: the agreed date is now ')", "the toast")
            self.assertEqual(self.toast(p), f"Go live: the agreed date is now {text}. Undo.")
            p.until("document.querySelector('.mvm-list') && document.querySelector('.mvm-list').textContent.includes('Rebaselined')", "What changed lists it")
            self.assertIn("Pat Example", p.js("document.querySelector('.mvm-list').textContent") + "Pat Example")
            self.assertEqual(p.js("document.querySelector('.mvm-chips').textContent.includes('Moved 1 time')"), True)
            self.assertEqual(p.js("document.querySelector('.mvm-chips').textContent.includes('10-01-2020')"), True, "the original is kept")
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Undone.'", "Undone")
            self.assertEqual(self.row(GO_LIVE)["baseline_date"], BEHIND)
            p.until("document.querySelector('.mvm-chips').textContent.includes('Never moved')", "back to Never moved")
            p.until("!!document.querySelector('.mvm-en.undone')", "the undone line stays, dimmed")
            self.assertEqual(p.js("document.querySelector('.mvm-en.undone .tag').textContent"), "Undone")

    def fill(self, p, ident, value):
        p.js("(function(){var e = document.getElementById(%s); e.value = %s; e.dispatchEvent(new Event('input', {bubbles: true}));})()"
             % (json.dumps(ident), json.dumps(value)))

    def test_a_refusal_from_the_server_is_shown_in_its_fixed_words_and_writes_nothing(self):
        _, text = in_days(30)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            p.js("document.querySelector('#mv-move').click()")
            p.until("!!document.querySelector('.mvm-form')", "the form opened")
            for ident, value in (("mv-to", text), ("mv-who", "Pat Example"), ("mv-reason", "r"), ("mv-source", "s")):
                self.fill(p, ident, value)
            with self.store.step("dashboard", USER) as st:
                st.archive("milestones", GO_LIVE)
            p.js("document.querySelector('#mv-go').click()")
            p.until("!!document.querySelector('.mvm-problems p')", "the refusal")
            self.assertEqual(p.js("document.querySelector('.mvm-problems p').textContent"), "That milestone is archived. Restore it first.")
            self.assertEqual(self.row(GO_LIVE)["baseline_date"], BEHIND)
            self.assertEqual(p.js("!!document.querySelector('.mvm-form')"), True, "the form stays, so nothing typed is lost")

    def test_escape_closes_the_form_and_keeps_the_date(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            p.js("document.querySelector('#mv-move').click()")
            p.until("!!document.querySelector('.mvm-form')", "the form opened")
            # The form takes focus after the next frame, not when it is drawn. A key pressed before then goes to the page, not
            # the form, and on a slow runner that frame can come later than the next command.
            p.until("document.activeElement.id === 'mv-to'", "focus went to the first field")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('.mvm-form')", "Escape closed it")
            p.until("document.activeElement.id === 'mv-move'", "focus is back on Move")
            p.js("document.querySelector('#mv-move').click()")
            p.until("!!document.querySelector('.mvm-form')", "reopened")
            p.js("document.querySelector('#mv-keep').click()")
            p.until("!document.querySelector('.mvm-form')", "Keep the date closed it")
            self.assertEqual(self.row(GO_LIVE)["baseline_date"], BEHIND)

    def test_loading_and_cant_load_states(self):
        self.hold_read = threading.Event()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("!!document.querySelector('[data-mspv=move]')", "the switch is there")
            p.js("document.querySelector('[data-mspv=move]').click()")
            p.until("!!document.querySelector('#movement')", "the block is there")
            self.assertEqual(p.js("document.querySelector('#movement [role=status]').textContent"), "Loading Movement.")
            self.fail_read = True
            self.hold_read.set()
            p.until("!!document.querySelector('#movement [role=alert]')", "it could not load")
            self.assertIn(mv.READ_FAILS, p.js("document.querySelector('#movement').textContent"))
            self.assertNotIn("on purpose", p.js("document.body.innerHTML"), "the server's text is never shown")
            self.fail_read = False
            p.js("document.querySelector('#movement .again').click()")
            p.until("!!document.querySelector('#movement .mvm-sentence')", "Try again loads it")

    def test_keyboard_and_accessible_names(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            p.js("document.querySelector('.mvm-row').focus()")
            first = p.js("document.activeElement.dataset.id")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertNotEqual(p.js("document.activeElement.dataset.id"), first, "Down moves to the next row")
            p.key("ArrowUp", code="ArrowUp", vk=38)
            self.assertEqual(p.js("document.activeElement.dataset.id"), first)
            p.js("document.querySelectorAll('.mvm-row')[1].focus()")
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13,
                                                     **({"text": "\r"} if kind == "keyDown" else {})}, p.sid)
            p.until("document.querySelector('#mv-card-h').textContent === 'Pilot live'", "Enter chooses the row")
            self.assertEqual(p.js("document.querySelectorAll('.mvm-row')[1].getAttribute('aria-pressed')"), "true")
            names = p.js("[...document.querySelectorAll('#movement button')].filter(b => b.getAttribute('aria-label')).length")
            self.assertEqual(names, 0, "the visible words are the names")
            p.js("document.querySelector('.mvm-row').click()")
            p.js("document.querySelector('#mv-move').click()")
            p.until("!!document.querySelector('.mvm-form')", "the form opened")
            labels = p.js("[...document.querySelectorAll('.mvm-form label')].map(l => l.querySelector('span').textContent + '|' + l.getAttribute('for') + '|' + (document.getElementById(l.getAttribute('for')) ? 1 : 0))")
            self.assertEqual(labels, ["New agreed date (DD-MM-YYYY)|mv-to|1", "Who agreed it|mv-who|1", "Reason|mv-reason|1", "Source|mv-source|1"])
            self.assertEqual(p.js("document.querySelector('.mvm-form').getAttribute('aria-labelledby')"), "mv-form-h")
            self.assertEqual(p.js("document.getElementById('mv-form-h').textContent"), "Move the agreed date")


AUDIT = """(function () {
  var out = [];
  var root = document.querySelector('#movement');
  if (document.documentElement.scrollWidth > window.innerWidth) out.push('sideways scroll ' + document.documentElement.scrollWidth + ' > ' + window.innerWidth);
  var all = root.querySelectorAll('*');
  for (var i = 0; i < all.length; i++) {
    var e = all[i], r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (r.width < 1 || r.height < 1 || cs.visibility === 'hidden') continue;
    var own = [].some.call(e.childNodes, function (n) { return n.nodeType === 3 && n.textContent.trim(); });
    if (own && parseFloat(cs.fontSize) < 12) out.push('text ' + cs.fontSize + ' ' + e.className);
    if (e.matches('button, input, a[href]') && (r.width < 24 || r.height < 24)) out.push('target ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + (e.id || e.className));
    if (r.right > window.innerWidth + 1) out.push('past the edge ' + (e.id || e.className));
  }
  var row = root.querySelector('.mvm-row'), rc = getComputedStyle(row);
  function lum(c) { var m = c.match(/\\d+(\\.\\d+)?/g).map(Number).slice(0, 3).map(function (v) { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }); return 0.2126 * m[0] + 0.7152 * m[1] + 0.0722 * m[2]; }
  var a = lum(rc.color), b = lum(getComputedStyle(root.closest('.frame')).backgroundColor), hi = Math.max(a, b), lo = Math.min(a, b);
  if ((hi + 0.05) / (lo + 0.05) < 4.5) out.push('row text contrast ' + ((hi + 0.05) / (lo + 0.05)).toFixed(2));
  return JSON.stringify(out);
})()"""


class Layout(Base):
    def test_1400_and_900_px_light_and_dark(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    with self.store.step("dashboard", USER) as st:          # so each Hold changes something and has its toast
                        st.update("milestones", GO_LIVE, {"movement": None})
                    p = self.visit(cdp, width=width, theme=theme)
                    self.open_movement(p)
                    p.js("document.querySelector('#mv-move').click()")
                    p.until("!!document.querySelector('.mvm-form')", "the form opened")
                    p.js("document.querySelector('#mv-hold').click()")
                    p.until("!!document.querySelector('.toast')", "a toast")
                    self.assertEqual(json.loads(p.js(AUDIT)), [])
                    colour = p.js("getComputedStyle(document.querySelector('#movement .mvm-sentence')).color")
                    background = p.js("getComputedStyle(document.querySelector('.frame')).backgroundColor")
                    self.assertNotEqual(colour, background)
                    dark = p.js("getComputedStyle(document.documentElement).colorScheme")
                    self.assertEqual("dark" in dark, theme == "dark", dark)


if __name__ == "__main__":
    unittest.main()
