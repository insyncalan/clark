"""#51: the project's one client contact, set on the Publish screen, and the Draft email it puts in a published
page. One contact per project; no warning about the address on the Publish screen.

Run: python3 dev/run_tests.py test_client_contact
  Rules      draft_email.contact_problem: one plain outside address, 254 characters at most, nothing hidden; plain words.
  Route      POST /api/client-contact through a real server (test_publish_route.Rig): the token, a bad or team address, other
             keys, one contact per project, history and Undo, Clear.
  Publish    the saved contact reaches the file only through publish.build's checked key; without one the file is byte for byte
             what it was before #51 and has no Draft email; no hidden or Sensitive row's text is in a file that carries one.
  Page       the field on the Publish screen in headless Chrome: add, change, clear, refuse, escaped, at 1400 and 900, light and dark.
Fictional data only (tests/fixtures/publish-plant.json; example.org and example.com addresses).
"""
import json
import re
import unittest
from pathlib import Path

import _publish_fixture as fx
from _paths import ROOT, SRC
from test_publish_dialog import Pg
from test_publish_route import DAY, EMPTY_BRANDING, USER, Rig
from test_page import navigate
from test_server import chrome

from clark import draft_email, page, publish, publish_flow, settings, server as sv
from clark.store import open_store

ROUTE = "/api/client-contact"
OWN = ["team.example.com"]
TEAM = "lead@team.example.com"
DANA = {"name": "Dana Hart", "email": "dana@client.example.org"}
PAGE_SRC = SRC / "clark" / "page" / "src"
DATA_BLOCK = re.compile(r'<script type="application/json" id="clark-data">(.*?)</script>', re.S)


def rig(case):
    r = Rig(case)
    (r.data_dir / settings.FILE).write_text(json.dumps({settings.OWN_DOMAINS: OWN}), encoding="utf-8")
    return r


def saved(r, code="PUB"):
    store = open_store(r.db, onedrive_roots=[])
    try:
        row = store.read("projects", ref=code)
    finally:
        store.close()
    return row["contact_name"], row["contact_email"]


def block(text):
    return json.loads(DATA_BLOCK.search(text).group(1))


class Rules(unittest.TestCase):
    def test_a_plain_outside_address_passes(self):
        for name, email in (("Dana Hart", "dana@client.example.org"), ("", " dana@client.example.org "), (None, "a.b+c@x.example.org")):
            self.assertIsNone(draft_email.contact_problem(name, email, OWN), email)

    def test_each_bad_contact_has_its_reason(self):
        cases = {"hidden": [("Dana", "dana​@client.example.org"), ("Da\nna", "dana@client.example.org"), ("Dana", "dana@client.example.org\r\nBcc: x@y.org"),
                            ("Dana‮", "dana@client.example.org")],
                 "no_address": [("Dana", ""), ("Dana", "   "), ("Dana", None)],
                 "too_long": [("Dana", "a" * 245 + "@example.org")],
                 "name_too_long": [("x" * 81, "dana@client.example.org")],
                 "not_one": [("Dana", "dana"), ("Dana", "a@b"), ("Dana", "a@b.org, c@d.org"), ("Dana", "a@b.org;c@d.org"),
                             ("Dana", "<a@b.org>"), ("Dana", "Dana <a@b.org>"), ("Dana", "a b@c.org"), ("Dana", ["a@b.org"]), (3, "a@b.org")],
                 "own_domain": [("Lee", TEAM), ("Lee", "LEAD@Team.Example.COM")]}
        for why, pairs in cases.items():
            for name, email in pairs:
                self.assertEqual(draft_email.contact_problem(name, email, OWN), why, (name, email))

    def test_the_limit_is_254_exactly(self):
        at = "@example.org"
        self.assertIsNone(draft_email.contact_problem("", "a" * (254 - len(at)) + at, OWN))
        self.assertEqual(draft_email.contact_problem("", "a" * (255 - len(at)) + at, OWN), "too_long")
        self.assertIsNone(draft_email.client_contact("", "a" * (255 - len(at)) + at, OWN), "publish drops it too")
        self.assertIsNone(draft_email.client_contact("", "dana​@client.example.org", OWN), "and a hidden character")

    def test_the_words_are_plain_and_say_the_next_step(self):
        for key, text in draft_email.CONTACT_WORDS.items():
            self.assertFalse(text.lower().startswith("clark"), key)
            self.assertTrue(text.endswith("then save."), key)
            self.assertNotRegex(text, r"(?i)\b(invalid|regex|rfc|domain list|error|null|string)\b|!", key)

    def test_the_own_domains_setting_keeps_only_plain_domain_names(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(settings.own_domains(d), [])
            Path(d, settings.FILE).write_text(json.dumps({settings.OWN_DOMAINS: ["Team.Example.com", "team.example.com", "not a domain", 4, "x", "a.example.org"]}), encoding="utf-8")
            self.assertEqual(settings.own_domains(d), ["team.example.com", "a.example.org"])
            Path(d, settings.FILE).write_text(json.dumps({settings.OWN_DOMAINS: "team.example.com"}), encoding="utf-8")
            self.assertEqual(settings.own_domains(d), [])

    def test_the_saved_profile_email_domain_counts_as_own_with_no_list(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(settings.own_domains(d), [])           # no profile email: nothing extra
            settings.set_profile(d, "Sam Lee", "sam@team.example.com")
            self.assertEqual(settings.own_domains(d), ["team.example.com"])
            Path(d, settings.FILE).write_text(json.dumps({settings.OWN_DOMAINS: ["a.example.org", "Team.Example.com"],
                                                          settings.PROFILE_EMAIL: "sam@team.example.com"}), encoding="utf-8")
            self.assertEqual(settings.own_domains(d), ["a.example.org", "team.example.com"])    # once, not twice
            own = settings.own_domains(d)
            self.assertEqual(draft_email.contact_problem("Dana", TEAM, own), "own_domain")
            self.assertEqual(draft_email.contact_problem("Dana", "x@mail.team.example.com", own), "own_domain")
            self.assertIsNone(draft_email.contact_problem("Dana", DANA["email"], own))


class Route(unittest.TestCase):
    def setUp(self):
        self.rig = rig(self)

    def post(self, body, **kw):
        return self.rig.call("POST", ROUTE, body, **kw)

    def test_it_refuses_without_the_token_or_with_a_wrong_one(self):
        for token in (False, "not-the-token"):
            status, got = self.post({"project": "PUB", "action": "save", **DANA}, token=token)
            self.assertEqual(status, 403, token)
            self.assertEqual(saved(self.rig), (None, None))

    def test_it_refuses_a_bad_address_in_plain_words_and_changes_nothing(self):
        for email in ("dana", "a@b.org, c@d.org", "dana​@client.example.org", "a" * 300 + "@example.org"):
            status, got = self.post({"project": "PUB", "action": "save", "name": "Dana", "email": email})
            self.assertEqual((status, got["ok"], got["code"]), (400, False, "contact_refused"), email)
            self.assertTrue(got["message"].endswith("then save."))
            self.assertEqual(saved(self.rig), (None, None))

    def test_it_refuses_a_team_address(self):
        status, got = self.post({"project": "PUB", "action": "save", "name": "Lee", "email": TEAM})
        self.assertEqual((status, got["code"], got["message"]), (400, "contact_refused", draft_email.CONTACT_WORDS["own_domain"]))
        self.assertEqual(saved(self.rig), (None, None))

    def test_it_fails_closed_on_any_other_shape(self):
        for body in ({"project": "PUB", "action": "save", **DANA, "extra": 1}, {"project": "PUB", "action": "clear", "email": DANA["email"]},
                     {"project": "PUB", "action": "set", **DANA}, {"project": "PUB", **DANA}, {"project": "pub", "action": "save", **DANA},
                     {"project": "PUB", "action": "save", "name": "Dana", "email": {"a": 1}}, [], "x"):
            status, got = self.post(body)
            self.assertEqual(status, 400, body)
            self.assertEqual(saved(self.rig), (None, None))
        status, got = self.post({"project": "NOPE", "action": "save", **DANA})
        self.assertEqual(status, 404)

    def test_a_big_body_is_refused_before_it_is_read(self):
        status, got = self.post({"project": "PUB", "action": "save", "name": "x" * 2000, "email": DANA["email"]})
        self.assertEqual((status, got["code"]), (400, "too_large"))
        self.assertEqual(sv.ROUTE_BODY_LIMITS[ROUTE], 1024)

    def test_save_then_undo_puts_the_old_value_back(self):
        self.assertEqual(self.post({"project": "PUB", "action": "save", **DANA})[0], 200)
        status, got = self.post({"project": "PUB", "action": "save", "name": "Sam Reed", "email": "sam@example.org"})
        self.assertEqual((status, got["changed"], got["contact"]), (200, True, {"name": "Sam Reed", "email": "sam@example.org"}))
        self.assertEqual(saved(self.rig), ("Sam Reed", "sam@example.org"))
        store = open_store(self.rig.db, onedrive_roots=[])
        try:
            fields = {r["field"] for r in store.step_rows(got["step"])}
            self.assertTrue({"contact_name", "contact_email"} <= fields, "in the history")
            store.undo(got["step"], USER)
        finally:
            store.close()
        self.assertEqual(saved(self.rig), (DANA["name"], DANA["email"]))

    def test_clear_and_the_same_again(self):
        self.post({"project": "PUB", "action": "save", **DANA})
        status, got = self.post({"project": "PUB", "action": "save", **DANA})
        self.assertEqual((status, got["changed"]), (200, False))
        status, got = self.post({"project": "PUB", "action": "clear"})
        self.assertEqual((status, got["changed"], got["contact"]), (200, True, None))
        self.assertEqual(saved(self.rig), (None, None))

    def test_one_contact_per_project(self):
        with self.rig.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "OTH", "name": "Other Programme"})
            st.update("projects", "OTH", {"contact_name": "Kim Rowe", "contact_email": "kim@other.example.org"})
        self.post({"project": "PUB", "action": "save", **DANA})
        self.assertEqual(saved(self.rig, "OTH"), ("Kim Rowe", "kim@other.example.org"))
        self.post({"project": "OTH", "action": "clear"})
        self.assertEqual(saved(self.rig), (DANA["name"], DANA["email"]))
        self.assertEqual(saved(self.rig, "OTH"), (None, None))

    def test_the_messages_are_plain_words(self):
        for key in ("contact_saved", "contact_cleared", "contact_unchanged", "contact_bad_action", "contact_failed"):
            text = publish_flow.MESSAGES[key]
            self.assertFalse(text.lower().startswith("clark"), key)
            self.assertNotRegex(text, r"(?i)\brequest\b|\bpath\b|!", key)
        self.assertNotRegex(" ".join(publish_flow.MESSAGES[k] for k in publish_flow.MESSAGES if k.startswith("contact")),
                            r"(?i)client's file|personal data|anyone who holds", "no warning about the address in the file (the owner)")


class Published(unittest.TestCase):
    def setUp(self):
        self.rig = rig(self)

    def published(self, **body):
        status, got = self.rig.publish(**body)
        self.assertEqual(status, 200, got)
        return (self.rig.local / "chosen.html").read_text(encoding="utf-8")

    def test_without_a_contact_the_file_is_what_it_was_before_and_has_no_button(self):
        before = publish.build(self.rig.store, "PUB", DAY, EMPTY_BRANDING)["body"]       # build with no contact arguments: as before #51
        text = self.published()
        self.assertEqual(text.encode("utf-8"), before)
        self.assertNotIn('"contact"', text)
        self.rig.call("POST", ROUTE, {"project": "PUB", "action": "save", **DANA})
        self.rig.call("POST", ROUTE, {"project": "PUB", "action": "clear"})
        self.assertEqual(self.published().encode("utf-8"), before, "cleared is the same as never set")

    def test_the_saved_contact_is_in_the_file_and_in_the_client_copy(self):
        self.rig.call("POST", ROUTE, {"project": "PUB", "action": "save", **DANA})
        text = self.published(to_client=True)
        self.assertEqual(block(text)["contact"], DANA)
        client = next(self.rig.client.iterdir()).read_text(encoding="utf-8")
        self.assertEqual(client, text)

    def test_preview_carries_it_too(self):
        self.rig.call("POST", ROUTE, {"project": "PUB", "action": "save", **DANA})
        status, got = self.rig.call("POST", "/api/preview", {"project": "PUB"})
        self.assertEqual(status, 200)
        body = self.rig.publisher.take_preview(got["url"].split("id=")[1]).decode("utf-8")
        self.assertEqual(block(body)["contact"], DANA)

    def test_a_team_address_written_past_the_route_still_never_reaches_a_file(self):
        with self.rig.store.step("dashboard", USER) as st:
            st.update("projects", "PUB", {"contact_name": "Lee", "contact_email": TEAM})
        text = self.published()
        self.assertNotIn('"contact"', text)
        self.assertNotIn(TEAM, text)

    def test_no_hidden_or_sensitive_row_reaches_a_file_that_carries_a_contact(self):
        self.rig.call("POST", ROUTE, {"project": "PUB", "action": "save", **DANA})
        text = self.published()
        data = block(text)
        self.assertEqual(data["contact"], DANA)
        markers = self.rig.plant["markers"]
        for item in self.rig.plant["dropped"]:                    # hidden, Sensitive and other excluded labels, flag off, archived
            if item in markers:
                for spelt in fx.spellings(markers[item]):
                    self.assertNotIn(spelt, text, item)
        offered = {r["id"] for kind in ("actions", "raid", "decisions") for r in data["data"].get(kind, [])}
        self.assertFalse(offered & set(self.rig.plant["dropped"]))
        self.assertNotIn("contact_email", json.dumps(data["data"]["project"]), "only the checked key, not the project's columns")

    def test_publish_inputs_never_reads_the_contact_columns(self):
        from clark.store import Invalid
        with self.assertRaises(Invalid):
            self.rig.store.publish_inputs("PUB", {**publish.PUBLISH_FIELDS, "projects": tuple(publish.PUBLISH_FIELDS["projects"]) + ("contact_email",)})


class Source(unittest.TestCase):
    def test_the_published_page_has_no_contact_field_or_route(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        for never in (ROUTE, "pub-contact", "Save contact", "No client contact yet"):
            self.assertNotIn(never, view, never)
        self.assertIn(ROUTE, page.PAGE.read_text(encoding="utf-8"))

    def test_only_publishApi_names_the_route(self):
        for f in PAGE_SRC.rglob("*"):
            if f.is_file() and f.name != "publishApi.js":
                self.assertNotIn(ROUTE, f.read_text(encoding="utf-8"), f.name)

    def test_the_field_shows_values_as_text_only(self):
        src = (PAGE_SRC / "edit" / "ClientContact.jsx").read_text(encoding="utf-8")
        self.assertNotIn("dangerouslySetInnerHTML", src)
        self.assertNotIn("innerHTML", src)

    def test_the_brd_records_the_hold_as_lifted(self):
        # The hold on this feature is lifted: FR-94, D-6 and the release list must not still say it is on hold.
        brd = (ROOT / "docs" / "BRD.md").read_text(encoding="utf-8")
        lines = brd.splitlines()
        i = next(n for n, line in enumerate(lines) if line.startswith("- **FR-94"))
        d6 = next(line for line in lines if line.startswith("| D-6 |"))
        self.assertNotIn("(on hold", lines[i])
        self.assertIn("hold lifted 31-10-2026", lines[i])
        self.assertIn("One contact per project", lines[i + 1])
        self.assertNotIn("On hold", d6)
        self.assertIn("**Decided**", d6)
        self.assertNotIn("(#51, on hold)", brd)


class Field(unittest.TestCase):
    def setUp(self):
        self.rig = rig(self)

    def show(self, cdp, width=1400, height=900):
        sid = navigate(cdp, self.rig.httpd.server_port, "#dashboard&p=PUB")
        p = Pg(self, cdp, sid)
        p.width(width, height)
        p.until("!!document.querySelector('#profile-btn')", "the top bar")
        p.open_publish()
        p.until("!!document.querySelector('#pub-contact')", "the contact field")
        return p

    def type(self, p, sel, text):
        p.js("(function(s, v){ const i = document.querySelector(s); i.value = v; i.dispatchEvent(new Event('input', {bubbles: true})); })(%s, %s)"
             % (json.dumps(sel), json.dumps(text)))

    def fill(self, p, name, email):
        p.js("document.querySelector('[data-contact-edit]').click()")
        p.until("!!document.querySelector('#pub-contact-email')", "the two fields")
        self.type(p, "#pub-contact-name", name)
        self.type(p, "#pub-contact-email", email)
        p.js("document.querySelector('[data-contact-save]').click()")

    def now(self, p):
        return p.js("document.querySelector('#pub-contact-now').innerText")

    def test_set_change_clear_and_refuse(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(self.now(p), "No client contact yet, so the page has no Draft email.")
            self.assertEqual(p.js("document.activeElement.id"), "pub-client", "focus still starts on To client")
            self.fill(p, "Lee", TEAM)
            p.until("!!document.querySelector('#pub-contact [role=alert] p')", "the refusal")
            self.assertEqual(p.js("document.querySelector('#pub-contact [role=alert]').innerText").strip(), draft_email.CONTACT_WORDS["own_domain"])
            self.assertEqual(saved(self.rig), (None, None))
            self.type(p, "#pub-contact-email", "a@b.org, c@d.org")
            p.js("document.querySelector('[data-contact-save]').click()")
            p.until("/single address/.test(document.querySelector('#pub-contact').innerText)", "one address only")
            self.type(p, "#pub-contact-name", DANA["name"])
            self.type(p, "#pub-contact-email", DANA["email"])
            p.js("document.querySelector('#pub-contact-email').dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', bubbles: true, cancelable: true}))")
            p.until("/Dana Hart/.test(document.querySelector('#pub-contact-now').innerText)", "saved with Enter")
            self.assertEqual(self.now(p), "Dana Hart · dana@client.example.org")
            self.assertEqual(saved(self.rig), (DANA["name"], DANA["email"]))
            self.assertTrue(p.js("!!document.querySelector('#publish-dialog[open]')"), "Enter saved the contact and did not publish")
            self.assertEqual(self.rig.rows(), [])
            self.assertNotRegex(p.dialog_text(), r"(?i)client's file|personal data|anyone who", "no warning (the owner)")
            p.js("document.querySelector('[data-contact-clear]').click()")
            p.until("/No client contact yet/.test(document.querySelector('#pub-contact-now').innerText)", "cleared")
            self.assertEqual(saved(self.rig), (None, None))

    def test_a_name_with_markup_is_shown_as_text(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.fill(p, "<b>Dana</b> & co", DANA["email"])
            p.until("/Dana/.test(document.querySelector('#pub-contact-now').innerText)", "saved")
            self.assertEqual(self.now(p), "<b>Dana</b> & co · dana@client.example.org")
            self.assertEqual(p.js("document.querySelectorAll('#pub-contact-now *').length"), 0)

    def test_it_fits_at_1400_and_900_in_light_and_dark(self):
        with chrome() as cdp:
            for width, height in ((1400, 900), (900, 700)):
                p = self.show(cdp, width, height)
                p.js("document.querySelector('[data-contact-edit]').click()")
                p.until("!!document.querySelector('#pub-contact-email')", "the form")
                self.type(p, "#pub-contact-email", "a" * 60 + "@client.example.org")
                for scheme in ("light", "dark"):
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                    got = p.js("(function(){ const d = document.querySelector('#publish-dialog').getBoundingClientRect(),"
                               " c = document.querySelector('#pub-contact').getBoundingClientRect(), i = document.querySelector('#pub-contact-email');"
                               " return [document.documentElement.scrollWidth <= innerWidth, d.left >= 0, d.right <= innerWidth,"
                               " c.left >= d.left, c.right <= d.right, getComputedStyle(i).color !== getComputedStyle(i).backgroundColor]; })()")
                    self.assertEqual(got, [True] * 6, (width, scheme))
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}, p.sid)
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('#publish-dialog')", "closed")


if __name__ == "__main__":
    unittest.main()
