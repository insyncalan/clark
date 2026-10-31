"""#51 (Draft email on the client page; BRD FR-94, FR-95): the builder that runs inside a published page, the contact a file
carries, and the dialog on the Work items page. Nothing is sent and nothing reaches clark: the page only copies.

Run: python3 dev/run_tests.py test_client_email
The repo has no Node, so the page's builder runs in headless Chrome (the #33 harness). Parts:
  Parity     the page's builder (src/clark/page/src/logic/draftEmailBuild.js) gives the same To, Subject, HTML, text, ticks and
             problems as src/clark/draft_email.py for the same input, and reads text the way confusables.skeleton does.
  Contact    publish puts a well-formed outside contact in the file, and leaves a team address, a malformed one and none out.
  Published  a file published from a store with a hidden row, an internal note and a team address, opened in Chrome: the
             Draft email dialog is there with the contact, and none of those is in any email it drafts (all three kinds, every
             item, all items), and the page asks for nothing outside itself. Without a contact there is no button.
Fictional data only (tests/fixtures/publish-plant.json).
"""
import contextlib
import copy
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

import _publish_fixture as fx  # noqa: E402
from clark import confusables, draft_email, publish  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_report_editor import EMPTY_BRANDING  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "client_email_demo.jsx"
MODES = draft_email.MODES                      # (update request, chase, decision); named from the module, never typed here
NOW = "2026-10-13 09:00"
OWN = ["team.example.com"]
TEAM_ADDRESS = "lead@team.example.com"
CONTACT = {"name": "Dana Hart", "email": "dana@client.example.org"}
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>'
                         f'<body><script>{script}</script></body></html>\n')
    return _PAGE["html"]


def item(id_, text, due=None, kind="actions", **kw):
    base = {"id": id_, "project": "ABC", "kind": kind, "text": text, "due": due, "priority": "Medium", "owner": "Dana Hart",
            "status": "Open", "client_visible": True}
    base.update(kw)
    return base


ITEMS = [
    item("ABC-A-001", "Share the UAT plan", "2026-10-09", priority="Urgent", update="Draft is with legal"),
    item("ABC-A-002", "Confirm the test dates <b>&</b> \"quote\" 'it'", "2026-10-15"),
    item("ABC-A-003", "A very long title " + "that goes on and on " * 6 + "and ends here", None),
    item("ABC-R-001", "Supplier may slip", "2026-10-30", kind="raid", type="Risk", priority="High"),
    item("ABC-R-002", "Gate closed", "2026-10-12", kind="raid", type="Issue", response="Agreed a workaround"),
    item("ABC-D-001", "Choose the cut-over weekend", "2026-10-14", kind="decisions", priority=""),
    item("ABC-A-004", "Hold the secret plan", "2026-10-16", text_extra=1),
    item("ABC-A-005", "The ‌confidential figure", "2026-10-16"),                      # a zero-width character in the word
    item("ABC-A-006", "Mark is rеstricted", "2026-10-16"),                            # a Cyrillic "е"
    item("ABC-A-007", "Hidden row", "2026-10-16", hidden=True),
]
CASES = []
for mode in MODES:
    for picked in (None, [], ["ABC-A-001"], ["ABC-D-001", "ABC-R-002", "ABC-A-002"]):
        for extra in ({}, {"include_update": True, "reply_by": "2026-10-20", "unblocks": "go-live"},
                      {"chased": {"ABC-A-001": {"n": 1, "last": "2026-10-06"}, "ABC-R-002": {"n": 2, "last": "2026-10-08"}}, "cover": "Hello all."},
                      {"chased": {"ABC-A-001": {"n": 3, "last": "2026-10-06"}}, "reply_by": "2026-10-19"},
                      {"from": "", "email": "", "name": ""}):
            CASES.append({"mode": mode, "picked": picked, "items": ITEMS, "name": "Dana Hart", "email": "dana@client.example.org",
                          "from": "Sam Lee", "own_domains": OWN, "now": NOW, "project_names": {"ABC": "Example Programme"}, **extra})
SHAPE = ("to", "subject", "html", "text", "ids", "problems", "ready", "tone", "mode", "internal_ids")


class InBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{cls.server.port}/"}, cls.sid)
        assert wait(lambda: cls.cdp.js("!!window.B", cls.sid)), "the test bundle ran"

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr[:80]}: {got}")
        return json.loads(got)


class Parity(InBrowser):
    def test_the_pages_builder_gives_the_same_email_as_the_python_builder(self):
        batch = self.val("%s.map(o => { const d = B.build(o); return %s; })" % (json.dumps(CASES), "{" + ",".join(f"{k}: d.{k}" for k in SHAPE) + "}"))
        self.assertEqual(len(batch), len(CASES))
        bad = []
        for opts, got in zip(CASES, batch):
            want = draft_email.build(copy.deepcopy(opts))
            want = {k: want[k] for k in SHAPE}
            if got != want:
                bad.append((opts["mode"], opts["picked"], [k for k in SHAPE if got[k] != want[k]]))
        self.assertEqual(bad, [], "the page's email differs from draft_email.build")

    def test_hidden_confidential_and_look_alike_rows_are_never_offered(self):
        got = self.val("B.build(%s)" % json.dumps({"mode": MODES[0], "items": ITEMS, "picked": None, "email": CONTACT["email"], "from": "Sam", "now": NOW}))
        for gone in ("ABC-A-005", "ABC-A-006", "ABC-A-007"):
            self.assertNotIn(gone, got["ids"])
            self.assertNotIn(gone, got["text"])
            self.assertNotIn(gone, got["html"])
        self.assertIn("ABC-A-001", got["ids"])

    def test_it_reads_text_the_way_the_python_scan_does(self):
        corpus = ["confidential", "CONFIDENTIAL", "conﬁdential", "ｃｏｎｆｉｄｅｎｔｉａｌ", "con​fidential", "cоnfidential",
                  "rеstricted", "res­tricted", "ŕestricted", "‐dash–—", "café", "plain words", "",
                  "ΑΒΕ АВЕ", "a\x0bb\x7fc", "x⠀y", "﷐z", "e\U000e0001f", "\U0001fffe!"]
        got = self.val("%s.map(s => B.skeleton(s))" % json.dumps(corpus))
        self.assertEqual(got, [confusables.skeleton(s) for s in corpus])

    def test_the_published_rows_become_the_items_an_email_can_be_drafted_from(self):
        data = {"project": {"code": "ABC"},
                "actions": [{"id": "ABC-A-001", "description": "Do it", "due_date": "2026-10-20", "priority": "High", "owner": "Dana", "status": "Open", "latest_update": "Started"},
                            {"id": "ABC-A-002", "description": "Done already", "status": "Closed"}],
                "raid": [{"id": "ABC-001", "type": "Risk", "description": "Might slip", "status": "Open", "priority": "Low", "internal_note": "SECRET"}],
                "decisions": [{"id": "ABC-D-001", "decision": "Pick a date", "needed_by": "2026-10-22", "made_by": "Sponsor", "status": "Pending"},
                              {"id": "ABC-D-002", "decision": "Made one", "status": "Made"}]}
        got = self.val("B.itemsOf(%s)" % json.dumps(data))
        self.assertEqual([i["id"] for i in got], ["ABC-A-001", "ABC-001", "ABC-D-001"])
        self.assertNotIn("SECRET", json.dumps(got))
        self.assertEqual(got[0]["update"], "Started")
        self.assertEqual(got[2]["due"], "2026-10-22")

    def test_the_contact_has_to_be_one_plain_address(self):
        good = self.val("B.contactOf({name: 'Dana Hart', email: ' dana@client.example.org '})")
        self.assertEqual(good, {"name": "Dana Hart", "email": "dana@client.example.org"})
        for bad in ({"name": "x", "email": "a@b"}, {"email": "a b@c.org"}, {"email": "a@c.org, b@c.org"}, {"email": "<a@c.org>"}, {"email": ""}, {"name": "x"}, None, "x"):
            self.assertIsNone(self.val("B.contactOf(%s)" % json.dumps(bad)), bad)


class Contact(unittest.TestCase):
    def test_an_outside_contact_is_kept_and_cut_to_plain_text(self):
        self.assertEqual(draft_email.client_contact("Dana\nHart", " dana@client.example.org ", OWN), {"name": "Dana Hart", "email": "dana@client.example.org"})
        self.assertEqual(len(draft_email.client_contact("x" * 500, "a@client.example.org")["name"]), draft_email.CONTACT_NAME_MAX)

    def test_a_team_address_a_bad_address_or_none_is_never_kept(self):
        for email in (TEAM_ADDRESS, "LEAD@TEAM.EXAMPLE.COM", "nobody", "a@b", "a@b.org\nbcc: x@y.org", "a@b.org, c@d.org", "<a@b.org>", "", None):
            self.assertIsNone(draft_email.client_contact("Dana", email, OWN), email)


def plant_with_team_address():
    """The publish plant with a team address planted where it must never reach a page: in a row left off the report, in the
    internal note of a milestone, and in a source path."""
    plant = fx.load()
    for a in plant["data"]["actions"]:
        if a["id"] == "PUB-A-011":
            a["description"] += f" write to {TEAM_ADDRESS}"
        if a["id"] == "PUB-A-001":
            a["source"] = f"{TEAM_ADDRESS}/actions.xlsx"
    plant["data"]["milestones"][0]["internal_note"] += f" {TEAM_ADDRESS}"
    return plant


class Published(InBrowser):
    """The file is opened in Chrome from disk; its own page runs the dialog."""
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="clark-client-email-")
        plant = plant_with_team_address()
        cls.store = open_store(fx.build_db(Path(cls.tmp) / "clark.db", plant), onedrive_roots=[])
        cls.plant = plant
        cls.out = Path(cls.tmp) / "out"
        cls.out.mkdir()
        cls.done = publish.publish(cls.store, "PUB", cls.out, by_user="Demo User", now="2026-10-28", branding=EMPTY_BRANDING,
                                   contact=CONTACT, own_domains=OWN)
        cls.text = Path(cls.done["path"]).read_text(encoding="utf-8")
        cls.stack = contextlib.ExitStack()
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()
        cls.store.close()
        shutil.rmtree(cls.tmp, True)

    def open(self, path=None, width=1400):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": "about:blank"}, self.sid)          # a fresh page each time, not a change of address in the old one
        self.cdp.call("Page.navigate", {"url": Path(path or self.done["path"]).as_uri() + "#work&p=PUB"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!document.querySelector('table.items, .empty')", self.sid)), "the Work items page drew")

    def click(self, selector):
        self.cdp.js(f"document.querySelector({json.dumps(selector)}).click()", self.sid)
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 120))", "awaitPromise": True}, self.sid)

    def markers(self):
        m = self.plant["markers"]
        every = [v for k, v in m.items() if k.startswith(("PUB", "internal", "source", "comment", "response", "reasoning", "options"))]
        return [x for x in every if isinstance(x, str)] + [TEAM_ADDRESS, "ZQ-HIDDEN-ACTION", "ZQ-INTERNAL-NOTE-M1", "ZQ-SOURCE-PATH"]

    def test_the_file_carries_the_contact_and_no_team_address_or_hidden_marker(self):
        block = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', self.text, re.S).group(1)
        self.assertEqual(json.loads(block)["contact"], CONTACT)
        for m in self.markers():
            self.assertNotIn(m, self.text, m)
        self.assertNotIn(TEAM_ADDRESS.split("@")[1], self.text)

    def test_the_dialog_drafts_to_the_contact_from_published_rows_only(self):
        self.open()
        self.assertTrue(self.cdp.js("!!document.querySelector('.cde-open')", self.sid), "the Draft email button")
        self.click(".cde-open")
        self.assertTrue(self.cdp.js("!!document.querySelector('.cde-box .de')", self.sid), "the dialog opened")
        self.assertEqual(self.cdp.js("[...document.querySelectorAll('.de-meta dd')][0].textContent", self.sid), CONTACT["email"])
        ticks = self.cdp.js("[...document.querySelectorAll('.pick input')].map(i => i.value)", self.sid)
        published = [a["id"] for a in self.plant["data"]["actions"] if a["id"] in self.plant["kept"]]
        self.assertTrue(set(published) & set(ticks))
        self.assertFalse(set(ticks) & set(self.plant["dropped"]), "no dropped row is offered")
        self.assertEqual(self.cdp.js("!![...document.querySelectorAll('.pk-foot button')].find(b => /I sent it/.test(b.textContent))", self.sid), False, "no history to write on a client page")
        self.assertTrue(self.cdp.js("[...document.querySelectorAll('.pk-foot .pk-btn')].some(b => /Copy for Outlook/.test(b.textContent))", self.sid))
        self.assertTrue(self.cdp.js("[...document.querySelectorAll('.pk-foot .pk-btn')].some(b => /Copy as text/.test(b.textContent))", self.sid))

    def test_a_name_is_needed_and_then_the_email_is_ready_to_copy(self):
        self.open()
        self.click(".cde-open")
        self.assertIn("name", self.cdp.js("document.querySelector('.de-problem').textContent", self.sid))
        self.cdp.js("(() => { const i = document.querySelector('.cde-from input'); i.value = 'Sam Lee'; i.dispatchEvent(new Event('input', {bubbles: true})); })()", self.sid)
        self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 120))", "awaitPromise": True}, self.sid)
        self.assertFalse(self.cdp.js("!!document.querySelector('.de-problem')", self.sid))
        self.assertIn("Sam", self.cdp.js("document.querySelector('.de-preview').textContent", self.sid))
        self.assertTrue(self.cdp.js("!![...document.querySelectorAll('.pk-foot a.pk-btn')].find(a => a.href.startsWith('mailto:dana%40client.example.org'))", self.sid), "Open in mail app")

    def test_no_kind_item_or_set_of_items_puts_a_hidden_row_an_internal_note_or_a_team_address_in_an_email(self):
        self.open()
        self.click(".cde-open")
        ids = self.cdp.js("[...document.querySelectorAll('.pick input')].map(i => i.value)", self.sid)
        self.assertTrue(len(ids) >= 3, ids)
        seen = 0
        for mode in ("update_request", "chase", "decision"):
            self.click(f'input[name="de-kind"][value="{mode}"]')
            self.cdp.js("(() => { const i = document.querySelector('.cde-from input'); i.value = 'Sam Lee'; i.dispatchEvent(new Event('input', {bubbles: true})); const c = document.querySelector('.de-opts input[type=checkbox]'); if (c && !c.checked) c.click(); })()", self.sid)
            for subset in [[i] for i in ids] + [ids]:
                self.cdp.js("(want => { for (const b of document.querySelectorAll('.pick input')) if (b.checked !== want.includes(b.value)) b.click(); })(%s)" % json.dumps(subset), self.sid)
                self.cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 40))", "awaitPromise": True}, self.sid)
                shown = self.cdp.js("document.querySelector('.de-meta').textContent + ' ' + document.querySelector('.de-preview').innerHTML + ' ' + document.querySelector('.de-preview').textContent", self.sid)
                for m in self.markers():
                    self.assertNotIn(m, shown, f"{m} in a {mode} email about {subset}")
                seen += 1
        self.assertGreater(seen, 6)
        self.assertNotIn(TEAM_ADDRESS, self.cdp.js("document.documentElement.outerHTML", self.sid))

    def test_a_row_has_an_envelope_that_opens_the_dialog_on_that_item_alone(self):
        self.open()
        first = self.cdp.js("document.querySelector('tr[data-id] .cde-row').closest('tr').dataset.id", self.sid)
        self.click("tr[data-id] .cde-row")
        self.assertEqual(self.cdp.js("[...document.querySelectorAll('.pick input:checked')].map(i => i.value)", self.sid), [first])
        self.assertEqual(self.cdp.js("location.hash", self.sid).count("item="), 0, "the envelope does not open the item's own page")
        self.cdp.js("document.querySelector('.de-kinds input').focus()", self.sid)
        self.cdp.js("document.querySelector('.de').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))", self.sid)
        self.assertFalse(self.cdp.js("!!document.querySelector('.cde-box')", self.sid), "Escape closes it")

    def test_the_page_asks_for_nothing_outside_itself(self):
        self.open()
        self.click(".cde-open")
        self.assertEqual(self.cdp.js("performance.getEntriesByType('resource').map(r => r.name).filter(n => !n.startsWith('data:') && !n.startsWith('file:')).length", self.sid), 0)
        self.assertEqual(self.cdp.js("typeof fetch === 'function' && !document.querySelector('form[action]')", self.sid), True)

    def test_there_is_no_button_when_the_file_carries_no_contact(self):
        for label, contact in (("none", None), ("a team address", {"name": "Lee", "email": TEAM_ADDRESS})):
            out = Path(self.tmp) / label.replace(" ", "-")
            out.mkdir()
            done = publish.publish(self.store, "PUB", out, by_user="Demo User", now="2026-10-28", branding=EMPTY_BRANDING, contact=contact, own_domains=OWN)
            text = Path(done["path"]).read_text(encoding="utf-8")
            self.assertNotIn('"contact"', text, label)
            self.assertNotIn(TEAM_ADDRESS, text, label)
            self.open(done["path"])
            self.assertFalse(self.cdp.js("!!document.querySelector('.cde-open, .cde-row')", self.sid), label)

    def test_it_fits_at_1400_and_900_in_light_and_dark(self):
        for width in (1400, 900):
            self.open(width=width)
            self.click(".cde-open")
            for scheme in ("light", "dark"):
                self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, self.sid)
                box = self.cdp.js("(() => { const r = document.querySelector('.cde-box').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, innerWidth, innerHeight]; })()", self.sid)
                self.assertGreaterEqual(box[0], 0, (width, scheme))
                self.assertLessEqual(box[1], box[4], (width, scheme))
                self.assertGreaterEqual(box[2], 0)
                self.assertLessEqual(box[3], box[5])
                self.assertEqual(self.cdp.js("document.documentElement.scrollWidth <= innerWidth", self.sid), True, "no sideways scroll")
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}, self.sid)


if __name__ == "__main__":
    unittest.main()
