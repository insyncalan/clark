"""#43: the Publish dialog and the client folder in Settings, in a real browser against the real routes.

Run: python3 dev/run_tests.py test_publish_dialog
Each test starts headless Chrome through the harness (tests/test_server.py chrome(): run_support's start_chrome and stop_chrome, so
it is stopped on exit) and a real server whose publisher is the real publish_flow over the #39 plant in a temporary folder. The
system's Save and folder windows are replaced through the publisher's two seams; the client folder and the Local folder are
temporary folders. Nothing is sent anywhere. Chrome is required: these tests fail, never skip, without it. Widths: 1400 and 900.
The non-browser checks (the published page names no publish route and holds no dialog) need no browser.
"""
import unittest
from pathlib import Path

from _paths import SRC
from test_page import navigate
from test_publish_route import Rig, WANTED
from test_server import chrome, wait

from unittest import mock

from clark import page, pdf, publish_pdf, to_client

PAGE_SRC = SRC / "clark" / "page" / "src"
NO_FOLDER = "No client folder yet. Set it in Settings."
DONE_NEW = to_client.MESSAGES["done_new"].format(name=WANTED)
WIDTHS = (1400, 900)


class Pg:
    def __init__(self, test, cdp, sid):
        self.t, self.cdp, self.sid = test, cdp, sid

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, seconds=15):
        self.t.assertTrue(wait(lambda: self.js(expr), seconds), what)

    def key(self, key, code=None, vk=0):
        for kind in ("keyDown", "keyUp"):
            self.cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code or key, "windowsVirtualKeyCode": vk,
                                                      "text": {" ": " ", "Enter": "\r"}.get(key, "") if kind == "keyDown" else ""}, self.sid)

    def width(self, w, h=900):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": h, "deviceScaleFactor": 1, "mobile": False}, self.sid)

    def open_publish(self):
        self.js("document.querySelector('#profile-btn').click()")
        self.until("!!document.querySelector('#profile-menu [data-kind=publish]')", "the menu opened")
        self.js("document.querySelector('#profile-menu [data-kind=publish]').click()")
        self.until("!!document.querySelector('#publish-dialog[open]')", "the dialog opened")

    def dialog_text(self):
        return self.js("document.querySelector('#publish-dialog').innerText")

    def go(self):
        self.js("document.querySelector('[data-go]').click()")

    def message(self):
        return self.js("(document.querySelector('#pub-msg') || {}).innerText || ''")

    def focused(self):
        return self.js("(function(){var e=document.activeElement;return e.id === 'profile-btn' ? 'publish' : e.id || e.tagName})()")


class Base(unittest.TestCase):
    saved = True

    def setUp(self):
        self.rig = Rig(self, saved=self.saved)

    def page(self, cdp, hash_="#dashboard&p=PUB"):
        sid = navigate(cdp, self.rig.httpd.server_port, hash_)
        p = Pg(self, cdp, sid)
        p.until("!!document.querySelector('#profile-btn')", "the profile circle is in the top bar")
        return p


class Dialog(Base):
    def test_C_dialog_defaults(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                p.open_publish()
                self.assertEqual(p.js("[document.querySelector('#pub-local').checked, document.querySelector('#pub-local').disabled]"),
                                 [True, True], "Local is ticked and cannot be changed")
                self.assertEqual(p.js("[document.querySelector('#pub-client').checked, document.querySelector('#pub-client').disabled]"),
                                 [False, False], "To client is unticked, and can be ticked: a folder is saved")
                text = p.dialog_text()
                self.assertIn("Copied to the client folder: Harbour Bridge", text)
                self.assertIn("Publish locally", text)
                self.assertNotIn("The client will see this page.", text)
                self.assertNotIn("Word", text, "no Word tick in v0.2")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('#publish-dialog')", "the dialog closed")

    def test_C_pdf_tick_is_there_unticked_and_never_remembered(self):
        with mock.patch.object(pdf, "find_chrome", return_value="/chrome"), chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                p.open_publish()
                self.assertEqual(p.js("[document.querySelector('#pub-pdf').checked, document.querySelector('#pub-pdf').disabled]"),
                                 [False, False], "PDF is unticked and can be ticked: Chrome is here")
                self.assertIn("PDF", p.dialog_text())
                p.js("document.querySelector('#pub-pdf').click()")
                p.until("document.querySelector('#pub-pdf').checked", "ticked")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('#publish-dialog')", "closed")
            p.open_publish()
            self.assertFalse(p.js("document.querySelector('#pub-pdf').checked"), "reopened: unticked")
            self.assertEqual(p.js("localStorage.length + sessionStorage.length"), 0)

    def test_C_pdf_tick_is_greyed_with_one_line_without_chrome(self):
        with mock.patch.object(pdf, "find_chrome", return_value=None), chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                p.open_publish()
                self.assertEqual(p.js("document.querySelector('#pub-pdf').disabled"), True)
                self.assertEqual(p.js("document.querySelector('#pub-pdf').closest('label').innerText.replace(/\\s+/g, ' ')"),
                                 "PDF " + publish_pdf.NO_CHROME_LINE)
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('#publish-dialog')", "closed")

    def test_C_pdf_words_follow_the_ticks(self):
        with mock.patch.object(pdf, "find_chrome", return_value="/chrome"), chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            self.assertIn("A PDF of the report, saved next to the report file. With To client ticked, it is copied to the client folder too.", p.dialog_text())
            p.js("document.querySelector('#pub-client').click()")
            p.until("!!document.querySelector('#pub-warn')", "the line about the client")
            self.assertEqual(p.js("document.querySelector('#pub-warn').innerText"), "The client will see this page.")
            p.js("document.querySelector('#pub-pdf').click()")
            p.until("document.querySelector('#pub-warn').innerText === 'The client will see this page and the PDF.'", "the line names the PDF")

    def test_C_tick_changes_button_and_line(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.until("document.querySelector('[data-go]').innerText === 'Publish and send to the client'", "the button changed")
            self.assertIn("The client will see this page.", p.dialog_text())
            p.js("document.querySelector('#pub-client').click()")
            p.until("document.querySelector('[data-go]').innerText === 'Publish locally'", "and back")
            self.assertNotIn("The client will see this page.", p.dialog_text())

    def test_C_keyboard(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.until("document.activeElement && document.activeElement.id === 'pub-client'", "focus starts on the To client tick")
            p.key(" ", code="Space", vk=32)
            p.until("document.querySelector('#pub-client').checked", "Space ticks it")
            p.key("Tab", code="Tab", vk=9)
            self.assertEqual(p.js("document.activeElement.id"), "pub-pdf", "Tab goes to the PDF tick (Chrome is here), then Cancel")
            p.key("Tab", code="Tab", vk=9)
            self.assertEqual(p.js("document.activeElement.hasAttribute('data-cancel')"), True, "then to the button")
            p.key("Tab", code="Tab", vk=9)
            self.assertEqual(p.js("document.activeElement.hasAttribute('data-go')"), True)
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#publish-dialog')", "Esc cancels")
            self.assertEqual(p.focused(), "publish", "focus returns to Publish")
            self.assertEqual((self.rig.everything_written(), self.rig.rows(), self.rig.saves), ([], [], []), "Esc published nothing")
            p.open_publish()
            self.assertFalse(p.js("document.querySelector('#pub-client').checked"), "reopened: unticked, never remembered")
            p.key("Enter", code="Enter", vk=13)         # Enter on the tick submits: Local only
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "Enter published")
            self.assertEqual(len(self.rig.rows()), 1)

    def test_C_reopen_is_unticked_after_a_client_publish(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.go()
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
            p.js("document.querySelector('[data-go]').click()")
            p.until("!document.querySelector('#publish-dialog')", "closed")
            self.assertEqual(p.focused(), "publish")
            p.open_publish()
            self.assertFalse(p.js("document.querySelector('#pub-client').checked"))
            self.assertEqual(p.js("localStorage.length + sessionStorage.length"), 0, "not remembered anywhere")

    def test_C_result_message_and_report_bar(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertEqual(p.js("document.querySelector('#pub-note')"), None, "nothing published yet")
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.go()
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
            self.assertEqual(p.message(), DONE_NEW)
            self.assertEqual((self.rig.client / WANTED).read_bytes(), (self.rig.local / "chosen.html").read_bytes())
            p.until("!!document.querySelector('#pub-note')", "the bar says when")
            self.assertRegex(p.js("document.querySelector('#pub-note').textContent"), r"^Published \d\d-\d\d-\d{4} to the client$")

    def test_C_publish_shows_a_spinner_while_it_works_then_a_tick_with_the_same_words(self):
        """#130 point 4: a spinner beside "Publishing…" (still when the person asked for less motion), then a tick beside the success line."""
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.js("window.__real = window.fetch; window.fetch = (u, o) => /publish/.test(String(u)) && o && o.method === 'POST' ? new Promise((ok) => { window.__release = () => ok(window.__real(u, o)); }) : window.__real(u, o);")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, p.sid)
            p.go()
            p.until("!!document.querySelector('#pub-msg [data-spin]')", "a spinner while it works")
            self.assertEqual(p.message().strip(), "Publishing…")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('[data-spin]')).animationName"), "pub-spin")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
            p.until("getComputedStyle(document.querySelector('[data-spin]')).animationName === 'none'", "the ring stays still for reduced motion")
            self.assertEqual(p.js("document.querySelector('#pub-msg [data-tick]')"), None, "no tick yet")
            p.js("window.__release()")
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
            self.assertEqual(p.js("document.querySelector('#pub-msg [data-spin]')"), None, "the spinner is gone")
            self.assertTrue(p.js("!!document.querySelector('#pub-msg .success [data-tick] svg')"), "a tick beside the line")
            self.assertRegex(p.message(), r"^Published\. Saved locally as ")

    def test_C_a_local_publish_says_locally_and_the_client_folder_is_left_alone(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.go()
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
            self.assertEqual(self.rig.listing(self.rig.client), [])
            p.until("!!document.querySelector('#pub-note')", "the bar says when")
            self.assertRegex(p.js("document.querySelector('#pub-note').textContent"), r"^Published \d\d-\d\d-\d{4} locally$")

    def test_C_cancelling_the_save_window_says_so_and_writes_nothing(self):
        self.rig.save_to = None
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.go()
            p.until("/Cancelled/.test(document.querySelector('#pub-msg').innerText)", "it says it was cancelled")
            self.assertEqual((self.rig.everything_written(), self.rig.rows()), ([], []))
            self.assertEqual(p.js("document.querySelector('[data-go]').disabled"), False, "the dialog is still usable")

    def test_C_clash_dialog(self):
        (self.rig.client / WANTED).write_bytes(b"<!doctype html>an earlier file")
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.go()
            p.until("!!document.querySelector('input[name=clash]')", "the question was asked")
            text = p.dialog_text()
            self.assertIn("A file with that name is already in the client folder", text)
            self.assertIn("saves as “PUB-report-2026-10-23 (2).html”", text)
            self.assertEqual(p.js("document.querySelector('input[name=clash]:checked').value"), "number", "Add a number is the default")
            self.assertEqual((self.rig.saves, len(self.rig.rows())), ([], 0), "nothing written, no Save window, yet")
            # Rename focuses its field and needs text
            p.js("document.querySelector('input[value=rename]').click()")
            p.until("!!document.querySelector('#pub-name')", "the name field")
            self.assertTrue(p.js("document.querySelector('[data-go]').disabled"), "Rename needs text")
            p.until("document.activeElement.id === 'pub-name'", "focus in the field")
            cdp.call("Input.insertText", {"text": "Week 43"}, p.sid)
            p.until("!document.querySelector('[data-go]').disabled", "text enables OK")
            # Overwrite needs its own confirmation and says there is no backup
            p.js("document.querySelector('input[value=overwrite]').click()")
            p.until("!!document.querySelector('#pub-confirm')", "the confirmation")
            self.assertIn("clark keeps no backup in the client folder", p.dialog_text())
            self.assertTrue(p.js("document.querySelector('[data-go]').disabled"))
            # Esc is Cancel: nothing written
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#publish-dialog')", "Esc cancels the question")
            self.assertEqual(p.focused(), "publish")
            self.assertEqual((self.rig.everything_written().count(str(Path("OneDrive-Fictional") / "Client reports" / "Harbour Bridge" / WANTED)),
                              self.rig.rows()), (1, []))
            # and Add a number goes through
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.go()
            p.until("!!document.querySelector('input[name=clash]')", "asked again")
            p.go()
            p.until("document.querySelector('[data-go]').innerText === 'Close'", "published")
            self.assertIn("PUB-report-2026-10-23 (2).html", p.message())
            self.assertEqual(self.rig.listing(self.rig.client), sorted([WANTED, "PUB-report-2026-10-23 (2).html"]))

    def test_C_a_failure_is_in_plain_words_in_an_alert(self):
        import shutil
        shutil.rmtree(self.rig.client)
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.go()
            p.until("document.querySelector('#pub-msg').getAttribute('role') === 'alert' && /Nothing was published/.test(document.querySelector('#pub-msg').innerText)", "the message")
            self.assertIn("isn't there", p.message())
            self.assertNotRegex(p.message(), r"(?i)error|exception|traceback|json|sha|errno")
            self.assertEqual((self.rig.rows(), self.rig.saves), ([], []))

    def test_C_fits_at_900(self):
        (self.rig.client / WANTED).write_bytes(b"<!doctype html>an earlier file")
        with chrome() as cdp:
            p = self.page(cdp)
            p.width(900, 700)
            for stage in ("choose", "clash"):
                if stage == "clash":
                    p.js("document.querySelector('#pub-client').click()")
                    p.go()
                    p.until("!!document.querySelector('input[name=clash]')", "the question")
                    p.js("document.querySelector('input[value=overwrite]').click()")
                else:
                    p.open_publish()
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), f"{stage}: no sideways scroll")
                box = p.js("(function(){var r=document.querySelector('[data-go]').getBoundingClientRect();"
                           "return [r.bottom <= window.innerHeight, r.right <= window.innerWidth, r.left >= 0]})()")
                self.assertEqual(box, [True, True, True], f"{stage}: the button is in view with no scrolling")
                dlg = p.js("(function(){var r=document.querySelector('#publish-dialog').getBoundingClientRect();return [r.left >= 0, r.right <= window.innerWidth]})()")
                self.assertEqual(dlg, [True, True])


class NoFolder(Base):
    saved = False

    def test_C_to_client_is_disabled_with_the_exact_words_until_a_folder_is_set(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            self.assertEqual(p.js("document.querySelector('#pub-client').disabled"), True)
            self.assertIn(NO_FOLDER, p.dialog_text())
            p.js("document.querySelector('#pub-client').click()")
            self.assertFalse(p.js("document.querySelector('#pub-client').checked"))
            self.assertEqual(p.js("document.querySelector('[data-go]').innerText"), "Publish locally")
            p.until("document.activeElement.hasAttribute('data-go')", "focus starts on the button when To client cannot be ticked")


class Settings(Base):
    saved = False

    def test_C_publishing_card_has_local_and_client(self):
        """A-S9: one Publishing card with a Local folder part (words only: no typed path) and the client folder part."""
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB")
            p.until("!!document.querySelector('#publishing')", "the card")
            self.assertEqual(p.js("document.querySelector('#publishing h2').innerText"), "Publishing")
            self.assertEqual(p.js("document.querySelector('#publishing #local-folder h3').innerText"), "Local folder")
            self.assertEqual(p.js("document.querySelector('#publishing #client-folder h3').innerText"), "Client folder")
            self.assertEqual(p.js("document.querySelectorAll('#publishing input').length"), 0, "no typed path or address")
            self.assertEqual(p.js("document.querySelectorAll('#publishing [data-choose-folder]').length"), 1)

    def test_C_settings_folder_field(self):
        self.rig.pick = self.rig.client
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB")
            p.until("!!document.querySelector('[data-choose-folder]')", "the field")
            self.assertIn("No client folder yet.", p.js("document.querySelector('#client-folder-now').innerText"))
            self.assertIn("a folder OneDrive syncs", p.js("document.querySelector('#client-folder').innerText"))
            p.js("document.querySelector('[data-choose-folder]').click()")
            p.until("/Harbour Bridge/.test(document.querySelector('#client-folder-now').innerText)", "the folder is shown")
            shown = p.js("document.querySelector('#client-folder-now').innerText")
            self.assertEqual(shown.strip(), "Harbour Bridge", "the folder's name only: no location of the person's computer")
            self.assertEqual(self.rig.store.read("projects", ref="PUB")["publish_client"], str(self.rig.client))
            self.assertTrue(p.js("!!document.querySelector('[data-clear-folder]')"))
            # a refusal is in a role=alert and changes nothing
            self.rig.pick = self.rig.data_dir
            p.js("document.querySelector('[data-choose-folder]').click()")
            p.until("document.querySelector('#client-folder [role=alert]') && /inside clark's own data folder/.test(document.querySelector('#client-folder [role=alert]').innerText)", "the refusal")
            self.assertEqual(self.rig.store.read("projects", ref="PUB")["publish_client"], str(self.rig.client))
            self.assertEqual(self.rig.listing(self.rig.client), [], "choosing writes nothing into the folder")
            # clearing
            p.js("document.querySelector('[data-clear-folder]').click()")
            p.until("/No client folder yet\\./.test(document.querySelector('#client-folder-now').innerText)", "cleared")
            self.assertIsNone(self.rig.store.read("projects", ref="PUB")["publish_client"])
            # and Publish now has To client disabled again
            p.js("document.querySelector('[data-view=dashboard]').click()")
            p.until("!!document.querySelector('#profile-btn')", "back")
            p.open_publish()
            self.assertTrue(p.js("document.querySelector('#pub-client').disabled"))

    def test_C_settings_fits_at_900(self):
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB")
            p.width(900, 700)
            p.until("!!document.querySelector('[data-choose-folder]')", "the field")
            self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))


class Published(unittest.TestCase):
    def test_the_published_page_names_no_publish_route_and_holds_no_dialog(self):
        text = page.VIEW_PAGE.read_text(encoding="utf-8")
        for never in ("/api/publish", "/api/client-folder", "/api/publication", "publish-dialog", "data-publish", "Choose folder",
                      "Publish and send to the client"):
            self.assertNotIn(never, text, never)
        self.assertIn("/api/publish", page.PAGE.read_text(encoding="utf-8"), "the served page has it")

    def test_only_publishApi_names_the_three_routes(self):
        for f in PAGE_SRC.rglob("*"):
            if f.is_file() and f.name != "publishApi.js":
                body = f.read_text(encoding="utf-8")
                for route in ("/api/publish", "/api/client-folder", "/api/publication"):
                    self.assertNotIn(route, body, f"{f.name} names {route}")

    def test_the_words_in_the_page_are_the_specs(self):
        src = "".join(f.read_text(encoding="utf-8") for f in PAGE_SRC.rglob("edit/*") if f.is_file())
        for key in ("button_local", "button_client", "client_sees", "not_saved"):
            self.assertIn(to_client.MESSAGES[key], src, key)
        for label in to_client.MESSAGES["clash_choices"][:3]:
            self.assertIn(label, src)
        self.assertNotRegex(src, r"report editor|(?<!X-)Clark\b")


if __name__ == "__main__":
    unittest.main()
