"""#43: the Publish dialog and the client folder in Settings, in a real browser against the real routes.

Run: python3 dev/run_tests.py test_publish_dialog
Each test starts headless Chrome through the harness (tests/test_server.py chrome(): run_support's start_chrome and stop_chrome, so
it is stopped on exit) and a real server whose publisher is the real publish_flow over the #39 plant in a temporary folder. The
system's Save and folder windows are replaced through the publisher's two seams; the client folder and the Local folder are
temporary folders. Nothing is sent anywhere. Chrome is required: these tests fail, never skip, without it. Widths: 1400 and 900.
The non-browser checks (the published page names no publish route and holds no dialog) need no browser.
"""
import re
import time
import unittest
from _editor_checks import for_project
from pathlib import Path

from _paths import SRC
from _new_page import reload_to_new_page_cdp
from test_page import navigate
from test_publish_route import Rig, WANTED, USER
from test_server import chrome, wait
import _testpage as testpage

from clark import page, to_client

PAGE_SRC = SRC / "clark" / "page" / "src"
NO_FOLDER = "No client folder yet. Set it in Settings, Publishing."
DONE_NEW = to_client.MESSAGES["done_new"].format(name=WANTED).replace("Published.", "Published (Publication 1).", 1)       # #120
WIDTHS = (1400, 900)


class Pg:
    def __init__(self, test, cdp, sid):
        self.t, self.cdp, self.sid = test, cdp, sid

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, seconds=15):
        self.t.assertTrue(wait(lambda: self.js(expr), seconds), what)

    def settled(self, what="the page settled", seconds=15):
        """Wait until nothing is moving: no running animation (document.getAnimations()) and window.scrollY the same on two reads 100 ms
        apart. A smooth scroll into view is not in getAnimations(), and macOS runs it longer than Linux, so a click or a measurement taken
        while it was still moving was the macOS gate's red."""
        seen = []

        def still():
            n, a = self.js("[document.getAnimations().length, window.scrollY]")
            time.sleep(0.1)
            b = self.js("window.scrollY")
            seen[:] = [n, a, b]
            return n == 0 and a == b
        self.t.assertTrue(wait(still, seconds), "%s: %s still moving after %d s (animations, scrollY then and 100 ms later: %s)" % (
            what, "an animation or the scroll was", seconds, seen))

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
        # the test copy of the served page (window.clarkPage): the finished dialog stays open until a test sets a time (#437)
        self.rig = Rig(self, saved=self.saved, page_html=testpage.html)

    def page(self, cdp, hash_="#dashboard&p=PUB"):
        sid = navigate(cdp, self.rig.httpd.server_port, for_project(hash_), section_style=None)      # the standard style is what these tests see (row 667)
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
                self.assertEqual(p.js("document.querySelector('#pub-to-set')"), None, "with a folder set there is nothing to set, so no link")
                self.assertIn("Publish locally", text)
                self.assertNotIn("The client will see this page.", text)
                self.assertIn("Also a Word document", text, "the Word tick (#48)")
                self.assertEqual(p.js("[document.querySelector('#pub-word').checked, document.querySelector('#pub-word').disabled]"), [False, False], "Also a Word document is unticked, and can be ticked")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('#publish-dialog')", "the dialog closed")

    def test_C_pdf_tick_is_there_unticked_and_never_remembered(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                p.open_publish()
                self.assertEqual(p.js("[document.querySelector('#pub-pdf').checked, document.querySelector('#pub-pdf').disabled]"),
                                 [False, False], "PDF is unticked and can be ticked: it needs nothing but the browser")
                self.assertEqual(p.js("document.querySelector('#pub-pdf').closest('label').querySelector('b').innerText"), "Also a PDF", "#453: the tick reads as the prototype's does")
                p.js("document.querySelector('#pub-pdf').click()")
                p.until("document.querySelector('#pub-pdf').checked", "ticked")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('#publish-dialog')", "closed")
            p.open_publish()
            self.assertFalse(p.js("document.querySelector('#pub-pdf').checked"), "reopened: unticked")
            self.assertEqual(p.js("localStorage.length + sessionStorage.length"), 0)

    def test_C_pdf_tick_has_no_chrome_wording_and_is_never_greyed(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                p.open_publish()
                self.assertFalse(p.js("document.querySelector('#pub-pdf').closest('label').classList.contains('off')"))
                self.assertNotIn("Chrome", p.dialog_text())
                self.assertEqual(p.js("document.querySelector('#pub-pdf').closest('label').innerText.replace(/\\s+/g, ' ')"),
                                 "Also a PDF The page as it prints: the tabs one after another, no controls, with the publication number in the foot")
                p.js("document.querySelector('[data-cancel]').click()")
                p.until("!document.querySelector('#publish-dialog')", "closed")

    def test_C_pdf_words_follow_the_ticks_and_the_client_line_never_names_the_pdf(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            self.assertEqual(p.js("!!document.querySelector('#pub-pdf-note')"), False, "no note until the PDF is ticked")
            p.js("document.querySelector('#pub-client').click()")
            p.until("!!document.querySelector('#pub-warn')", "the line about the client")
            p.js("document.querySelector('#pub-pdf').click()")
            p.until("!!document.querySelector('#pub-pdf-note')", "the note about the print box")
            self.assertEqual(p.js("document.querySelector('#pub-warn').innerText"), to_client.MESSAGES["client_sees"])
            self.assertIn("untick Headers and footers", p.js("document.querySelector('#pub-pdf-note').innerText"))

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
            self.assertEqual(p.js("document.activeElement.id"), "pub-word", "Tab goes to the Word tick, then the PDF tick (row 796)")
            p.key("Tab", code="Tab", vk=9)
            self.assertEqual(p.js("document.activeElement.id"), "pub-pdf", "Tab goes to the PDF tick, then Cancel")
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
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "Enter published")
            self.assertEqual(len(self.rig.rows()), 1)

    def test_C_row_796_order_title_weight_size_heading_and_tab_at_both_widths_in_light_and_dark(self):
        # row 796: Local, To client, Word, PDF; titles at the box's text size in the medium weight; the heading is the one every .dlg box has
        with chrome() as cdp:
            p = self.page(cdp)
            for theme in Finished.THEMES:
                for w in WIDTHS:
                    where = f"{theme} {w}"
                    Finished.look(self, p, theme, w)
                    p.open_publish()
                    p.until("document.getAnimations().length === 0", where + ": the box has finished opening")
                    self.assertEqual(p.js("Array.from(document.querySelectorAll('#publish-dialog .pubopts > label input')).map(function(i){return i.id})"),
                                     ["pub-local", "pub-client", "pub-word", "pub-pdf"], where + ": Local, To client, Word, PDF")
                    self.assertEqual(p.js("Array.from(document.querySelectorAll('#publish-dialog .pubopt b')).map(function(b){return b.innerText})"),
                                     ["Local", "To client", "Also a Word document", "Also a PDF"], where)
                    body = p.js("getComputedStyle(document.querySelector('#publish-dialog .pubopt')).fontSize")
                    med = p.js("getComputedStyle(document.documentElement).getPropertyValue('--weight-medium').trim()")      # the token (600 in this build)
                    self.assertIn(med, ("500", "600"), where)
                    self.assertEqual(p.js("Array.from(document.querySelectorAll('#publish-dialog .pubopt b')).map(function(b){var c=getComputedStyle(b);return [c.fontWeight,c.fontSize]})"),
                                     [[med, body]] * 4, where + ": weight var(--weight-medium), size the box's own")
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('#publish-dialog')).fontSize"), body, where + ": the box's body size")
                    # the heading equals another box's heading: a probe .dlg h2, which every other box has
                    head = p.js("(function(){var d=document.createElement('dialog');d.className='dlg';d.innerHTML='<h2>x</h2>';document.body.appendChild(d);"
                                "var a=getComputedStyle(d.firstChild),b=getComputedStyle(document.querySelector('#pub-title'));"
                                "var r=[a.fontSize,a.fontWeight,b.fontSize,b.fontWeight];d.remove();return r})()")
                    self.assertEqual(head[:2], head[2:], where + ": the heading is the other boxes' heading")
                    self.assertEqual(p.js("Math.round(document.querySelector('#publish-dialog').getBoundingClientRect().width)"), 560, where)
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), where + ": no sideways scroll")
                    # Tab: from the To client tick, Word, PDF, Cancel, Publish; the focus ring shows
                    p.js("document.querySelector('#pub-client').focus()")
                    seen = []
                    for _ in range(4):
                        p.key("Tab", code="Tab", vk=9)
                        seen.append(p.js("(function(){var e=document.activeElement;return e.id || (e.hasAttribute('data-cancel') ? 'cancel' : e.hasAttribute('data-go') ? 'go' : e.tagName)})()"))
                    self.assertEqual(seen, ["pub-word", "pub-pdf", "cancel", "pub-go"], where + ": Tab order")
                    p.js("document.querySelector('#pub-word').focus()")
                    self.assertNotEqual(p.js("getComputedStyle(document.querySelector('#pub-word').closest('.pubopt')).outlineStyle"), "none", where + ": focus ring shows")
                    p.js("document.querySelector('[data-cancel]').click()")
                    p.until("!document.querySelector('#publish-dialog')", where + ": closed")

    def test_C_reopen_is_unticked_after_a_client_publish(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.go()
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
            p.js("document.querySelector('[data-go]').click()")
            p.until("!document.querySelector('#publish-dialog')", "closed")
            self.assertEqual(p.focused(), "publish")
            p.open_publish()
            self.assertFalse(p.js("document.querySelector('#pub-client').checked"))
            self.assertEqual(p.js("localStorage.length + sessionStorage.length"), 0, "not remembered anywhere")

    def test_C_result_message_and_report_bar(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertEqual(p.js("document.querySelector('#report-state').textContent"), "Draft · not published yet", "nothing published yet")
            p.open_publish()
            p.js("document.querySelector('#pub-client').click()")
            p.go()
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
            self.assertEqual(p.message(), DONE_NEW)
            self.assertEqual((self.rig.client / WANTED).read_bytes(), (self.rig.local / "chosen.html").read_bytes())
            p.until("/^Published/.test(document.querySelector('#report-state').textContent)", "the bar says when")
            self.assertRegex(p.js("document.querySelector('#report-state').textContent"), r"^Published \d\d-\d\d-\d{4} to the client$")

    def test_C_publish_shows_a_spinner_while_it_works_then_a_tick_with_the_same_words(self):
        """#130 point 4: a spinner on the Publish button beside "Publishing…" (still when the person asked for less motion), then a tick beside the success line."""
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.js("window.__real = window.fetch; window.fetch = (u, o) => /publish/.test(String(u)) && o && o.method === 'POST' ? new Promise((ok) => { window.__release = () => ok(window.__real(u, o)); }) : window.__real(u, o);")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "no-preference"}]}, p.sid)
            p.go()
            p.until("!!document.querySelector('[data-go] [data-spin]')", "a spinner while it works")
            self.assertEqual(p.message().strip(), "Publishing…")
            self.assertEqual(p.js("getComputedStyle(document.querySelector('[data-spin]')).animationName"), "pub-spin")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, p.sid)
            p.until("getComputedStyle(document.querySelector('[data-spin]')).animationName === 'none'", "the ring stays still for reduced motion")
            self.assertEqual(p.js("document.querySelector('[data-go] [data-tick]')"), None, "no tick yet")
            p.js("window.__release()")
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
            self.assertEqual(p.js("document.querySelector('[data-go] [data-spin]')"), None, "the spinner is gone")
            self.assertTrue(p.js("!!document.querySelector('[data-go] [data-tick] svg')"), "a tick on the button")
            self.assertRegex(p.message(), r"^Published \(Publication \d+\)\. Saved locally as ")

    def test_C_a_local_publish_says_locally_and_the_client_folder_is_left_alone(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.go()
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
            self.assertEqual(self.rig.listing(self.rig.client), [])
            p.until("/^Published/.test(document.querySelector('#report-state').textContent)", "the bar says when")
            self.assertRegex(p.js("document.querySelector('#report-state').textContent"), r"^Published \d\d-\d\d-\d{4} locally$")

    def test_C_view_shows_the_published_chip_and_only_the_week_box_after_a_publish(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.go()
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
            p.go()
            p.until("!document.querySelector('#publish-dialog[open]')", "the dialog closed")
            p.until("/^Published/.test(document.querySelector('#report-state').textContent)", "the chip says when")
            self.assertEqual(p.js("document.querySelector('#report').dataset.mode"), "view")
            self.assertRegex(p.js("document.querySelector('#report-state').textContent"), r"^Published \d\d-\d\d-\d{4} locally$")
            self.assertEqual(p.js("document.querySelectorAll('.rbar input').length"), 1, "View's one field is the week ending box (#439)")

    def test_C_the_dialog_line_says_which_publication_this_will_be_and_when_the_last_one_went(self):
        """#437 row 26 (the prototype's io.js): 'this will be Publication N' and, once there is one, 'last published <date>, locally'."""
        sub = "document.querySelector('#pub-sub').textContent"
        with chrome() as cdp:
            p = self.page(cdp)
            p.open_publish()
            p.until("/this will be Publication 1/.test(" + sub + ")", "the first one says it will be number 1")
            self.assertNotIn("last published", p.js(sub), "no earlier one yet")
            self.assertNotIn("Published (", p.js(sub))
            p.go()
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
            p.go()
            p.until("!document.querySelector('#publish-dialog[open]')", "the dialog closed")
            p.open_publish()
            p.until("/this will be Publication 2/.test(" + sub + ")", "the next one says it will be number 2")
            self.assertRegex(p.js(sub), r"this will be Publication 2 · last published \d\d-\d\d-\d{4}, locally$")

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
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
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


class Finished(Base):
    """#437: the warning's second sentence (rows 29 and 56), and the finished state (rows 27 and 57): the tick and "Published
    (Publication N)" on the button, then the dialog closes by itself and a note with no Undo says what was done (the prototype's
    io.js, 1200 ms). The test build keeps the dialog open until a test sets a time (testhook.js publishCloseMs), so nothing here
    waits the real 1200 ms."""

    THEMES = ("light", "dark")

    def look(self, p, theme, w):
        p.width(w)
        p.js("document.documentElement.dataset.theme = 'dark'" if theme == "dark" else "delete document.documentElement.dataset.theme")
        motion = "reduce" if theme == "dark" else "no-preference"        # the dark pass also asks for less motion
        p.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": motion}]}, p.sid)

    def fits(self, p, selector, where):
        self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), where + ": no sideways scroll")
        box = p.js("(function(){var r=document.querySelector(\"" + selector + "\").getBoundingClientRect();return [r.width > 0, r.left >= 0, r.right <= window.innerWidth]})()")
        self.assertEqual(box, [True, True, True], where + ": " + selector + " is in view")
        ink = p.js("(function(){var e=document.querySelector(\"" + selector + "\"),c=getComputedStyle(e).color,b=e,bg='rgba(0, 0, 0, 0)';"
                   "while(b&&(bg=getComputedStyle(b).backgroundColor)==='rgba(0, 0, 0, 0)')b=b.parentElement;return [c, bg]})()")
        self.assertNotEqual(ink[0], ink[1], where + ": the words show against their background")

    def test_C_the_warning_has_both_sentences_at_both_widths_in_light_and_dark(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for theme in self.THEMES:
                for w in WIDTHS:
                    where = f"{theme} {w}"
                    self.look(p, theme, w)
                    p.open_publish()
                    p.js("document.querySelector('#pub-client').click()")
                    p.until("!!document.querySelector('#pub-warn')", where + ": the warning")
                    self.assertEqual(p.js("document.querySelector('#pub-warn').innerText"),
                                     "The client will see this page. Only what is shown in View mode is included.", where)
                    self.fits(p, "#pub-warn", where)
                    p.js("document.querySelector('[data-cancel]').click()")
                    p.until("!document.querySelector('#publish-dialog')", where + ": closed")

    def test_C_the_finished_dialog_closes_by_itself_and_a_note_with_no_undo_says_what_was_done(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertEqual(p.js("JSON.stringify(window.clarkPage.publishCloseMs())"), '{"now":null,"page":1200}',"the page's own wait is the prototype's 1200 ms")
            n = 0
            for theme in self.THEMES:
                for w in WIDTHS:
                    where, n = f"{theme} {w}", n + 1
                    self.look(p, theme, w)
                    p.js("window.clarkPage.publishCloseMs(null)")          # held open first, to read the finished button
                    p.open_publish()
                    p.go()
                    p.until("document.querySelector('[data-go]').classList.contains('ok')", where + ": published")
                    self.assertEqual(p.js("document.querySelector('[data-go]').innerText.trim()"), f"Published (Publication {n})", where)
                    self.assertTrue(p.js("!!document.querySelector('[data-go] [data-tick] svg')"), where + ": the tick")
                    self.fits(p, "[data-go]", where)
                    p.js("document.querySelector('[data-go]').click()")
                    p.until("!document.querySelector('#publish-dialog')", where + ": closed by its button")
                    n += 1                                                   # now one that closes by itself
                    p.js("window.clarkPage.publishCloseMs(50)")
                    p.open_publish()
                    p.go()
                    p.until("!document.querySelector('#publish-dialog')", where + ": the dialog closed by itself")
                    self.assertEqual(len(self.rig.rows()), n, where + ": it published")
                    find = ("[...document.querySelectorAll('.toasts .toast')].find(t => t.querySelector('.toast-text').innerText"
                            f".startsWith('Published (Publication {n}).'))")
                    p.until("!!" + find, where + ": the note")
                    self.assertEqual(p.js(find + ".dataset.kind"), "done", where)
                    self.assertRegex(p.js(find + ".querySelector('.toast-text').innerText"), rf"^Published \(Publication {n}\)\. Saved locally as ", where)
                    self.assertEqual(p.js("[..." + find + ".querySelectorAll('button')].map(b => b.innerText.trim())"), ["Close"], where + ": no Undo, only Close")
                    self.assertEqual(p.js(find + ".querySelector('[data-undo]')"), None, where)
                    self.assertEqual(p.focused(), "publish", where + ": focus is back on the profile circle, where Publish was")
                    p.js("window.__note = " + find + ".querySelector('.toast-text'); window.__note.id = 'pub-note-" + str(n) + "'")
                    self.fits(p, f"#pub-note-{n}", where)

    def test_C_a_late_timer_never_closes_a_later_dialog(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.js("window.clarkPage.publishCloseMs(1500)")
            p.open_publish()
            p.go()
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published")
            p.js("document.querySelector('[data-go]').click()")                # closed by hand before the timer
            p.until("!document.querySelector('#publish-dialog')", "closed")
            p.open_publish()                                                   # a fresh dialog, not finished
            self.assertFalse(wait(lambda: not p.js("!!document.querySelector('#publish-dialog[open]')"), 3), "the old timer left the new dialog open")
            self.assertEqual(p.focused(), "pub-client", "focus is still in the new dialog")


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


    def test_C_set_it_in_settings_publishing_is_a_link_to_the_publishing_card(self):
        """D-14 (prototype io.js #pubToSet): the words "Settings, Publishing" are a link; it closes the box, opens Settings, and the
        Publishing card is in view and has the focus. Both widths."""
        with chrome() as cdp:
            p = self.page(cdp)
            for w in WIDTHS:
                p.width(w)
                p.js("document.querySelector('[data-view=dashboard]').click()")
                p.open_publish()
                self.assertEqual(p.js("(function(){var b=document.querySelector('#pub-client + span small button');return b&&[b.tagName,b.textContent,b.type,b.getBoundingClientRect().height>=24]})()"),
                                 ["BUTTON", "Settings, Publishing", "button", True], f"{w}: a link of its own, at least 24 px to point at")
                self.assertEqual(p.js("document.querySelector('#pub-client + span small').textContent"), NO_FOLDER, "the sentence reads whole")
                self.assertEqual(p.js("document.querySelector('#pub-client').checked"), False, "pressing the link does not tick the box")
                p.js("document.querySelector('#pub-to-set').click()")
                p.until("!document.querySelector('#publish-dialog') && document.activeElement && document.activeElement.id === 'publishing'", f"{w}: the box closed and the Publishing card has the focus")
                self.assertEqual(p.js("document.querySelector('h1').textContent"), "Settings", "Settings is open")      # row 976: Settings is no tab, so the page's own heading says it is open
                self.assertEqual(p.js("document.querySelectorAll('[data-view=settings]').length"), 0, "and it is not a tab")
                self.assertTrue(p.js("(function(){var r=document.querySelector('#publishing').getBoundingClientRect();return r.top >= 0 && r.top < innerHeight})()"), "the card is in view")
                self.assertTrue(p.js("(function(){var t=document.querySelector('header.top').getBoundingClientRect().bottom;return document.querySelector('#publishing').getBoundingClientRect().top >= t - 1})()"), "clear of the top bar")


class Settings(Base):
    saved = False

    def test_C_publishing_card_has_local_and_client(self):
        """A-S9: one Publishing card with a Local folder part (words only: no typed path) and the client folder part."""
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB&s=folder")
            p.until("!!document.querySelector('#publishing')", "the card")
            self.assertEqual(p.js("document.querySelector('#publishing h2').innerText"), "Publishing")
            self.assertEqual(p.js("document.querySelector('#publishing #local-folder h3').innerText"), "Local folder")
            self.assertEqual(p.js("document.querySelector('#publishing #client-folder h3').innerText"), "Client folder")
            # item 647 (the owner's yes): one box, under Choose folder, for a pasted folder path; the Local part has none
            self.assertEqual(p.js("document.querySelectorAll('#publishing input').length"), 1, "only the client folder's paste box")
            self.assertEqual(p.js("document.querySelectorAll('#publishing #client-folder-paste').length"), 1)
            self.assertEqual(p.js("document.querySelectorAll('#publishing [data-choose-folder]').length"), 1)

    def test_C_settings_folder_field(self):
        self.rig.pick = self.rig.client
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB&s=folder")
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

    def test_C_settings_local_folder(self):
        """Row 852: Choose folder under Local folder saves once; the toast says 'Local folder saved' with Undo; Clear puts none back."""
        with self.rig.store.step("dashboard", USER) as st:      # the plant carries a made-up Local folder; this starts with none
            st.update("projects", "PUB", {"publish_local": None})
        mine = self.rig.root / "My reports"
        mine.mkdir()
        self.rig.pick = mine
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB&s=folder")
            p.until("!!document.querySelector('[data-choose-local]')", "the Local folder's button")
            self.assertEqual(p.js("document.querySelector('#local-folder-now').innerText.trim()"), "No local folder yet.")
            p.js("document.querySelector('[data-choose-local]').click()")
            p.until("document.querySelector('#local-folder-now').innerText.trim() === 'My reports'", "the folder is shown by its name")
            self.assertEqual(self.rig.store.read("projects", ref="PUB")["publish_local"], str(mine))
            self.assertEqual(p.js("document.querySelector('.toast .toast-text').innerText"), "Local folder saved")
            self.assertIsNone(self.rig.store.read("projects", ref="PUB")["publish_client"], "the client folder is untouched")
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("document.querySelector('#local-folder-now').innerText.trim() === 'No local folder yet.'", "Undo puts it back")
            self.assertIsNone(self.rig.store.read("projects", ref="PUB")["publish_local"])
            p.js("document.querySelector('[data-choose-local]').click()")
            p.until("!!document.querySelector('[data-clear-local]')", "Clear")
            p.js("document.querySelector('[data-clear-local]').click()")
            p.until("document.querySelector('#local-folder-now').innerText.trim() === 'No local folder yet.'", "cleared")
            self.assertIsNone(self.rig.store.read("projects", ref="PUB")["publish_local"])

    def test_C_settings_fits_at_900(self):
        with chrome() as cdp:
            p = self.page(cdp, "#settings&p=PUB&s=folder")
            p.width(900, 700)
            p.until("!!document.querySelector('[data-choose-folder]')", "the field")
            self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))


PLACEHOLDER_ONE = "1 work item still has a placeholder title ({t}) and will be shown to the client. Rename it or turn off its eye first."
PLACEHOLDER_MANY = ("{n} work items still have a placeholder title (such as {t}) and will be shown to the client. "
                    "Rename them or turn off their eye first.")


class Placeholder(Base):
    """Item 449: every work item is client-visible by default (D-3), so the dialog warns while one the client would see still has
    the title Add gave it. A warning, not a block: Publish still works."""

    def change(self, body):
        status, reply = self.rig.call("POST", "/api/change", {"project": "PUB", "place": "menu", **body})
        self.assertEqual(status, 200, reply)
        return reply

    def page(self, cdp, hash_="#dashboard&p=PUB"):
        p = super().page(cdp, hash_)
        # the same address again is only a hash change: load the data afresh
        reload_to_new_page_cdp(cdp, p.sid, "!!document.querySelector('#profile-btn')", "the page loaded again")
        return p

    def add(self, table, values):
        return str(self.change({"kind": table, "op": "new", "values": values})["ref"])

    def warning(self, p, w, scheme):
        p.width(w)
        self.cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        p.open_publish()
        found = p.js("(function(){var e=document.querySelector('#pub-placeholder');return e ? [e.innerText, e.dataset.count] : null})()")
        self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))
        p.js("document.querySelector('[data-cancel]').click()")
        p.until("!document.querySelector('#publish-dialog')", "the dialog closed")
        return found

    def each(self, cdp, expected):
        for w in WIDTHS:
            for scheme in ("light", "dark"):
                with self.subTest(width=w, scheme=scheme):
                    p = self.page(cdp)
                    self.assertEqual(self.warning(p, w, scheme), expected)

    def test_the_warning_counts_placeholder_items_the_client_would_see_and_goes_when_renamed_or_hidden(self):
        with chrome() as cdp:
            self.cdp = cdp
            self.each(cdp, None)                                                           # the plant has none
            a = self.add("actions", {"description": "New action"})
            r = self.add("raid", {"type": "Risk", "description": "New risk"})
            self.add("raid", {"type": "Issue", "description": "New risk"})                # an issue called New risk is a real title
            self.each(cdp, [PLACEHOLDER_MANY.format(n=2, t="New action"), "2"])
            self.change({"kind": "actions", "op": "update", "id": a, "changes": {"description": "Order the steel"}})
            self.each(cdp, [PLACEHOLDER_ONE.format(t="New risk"), "1"])
            self.change({"kind": "raid", "op": "update", "id": r, "changes": {"client_visible": 0}})
            self.each(cdp, None)
            # the warning never blocks Publish
            self.change({"kind": "raid", "op": "update", "id": r, "changes": {"client_visible": 1}})
            p = self.page(cdp)
            p.open_publish()
            self.assertEqual(p.js("document.querySelector('#pub-placeholder').innerText"), PLACEHOLDER_ONE.format(t="New risk"))
            self.assertFalse(p.js("document.querySelector('[data-go]').disabled"))
            p.go()
            p.until("document.querySelector('[data-go]').classList.contains('ok')", "published with the warning shown")
            self.assertEqual(len(self.rig.rows()), 1)


class Published(unittest.TestCase):
    def test_the_published_page_names_no_publish_route_and_holds_no_dialog(self):
        text = page.VIEW_PAGE.read_text(encoding="utf-8")
        for never in ("/api/publish", "/api/client-folder", "/api/publication", "publish-dialog", "data-publish", "Choose folder",
                      "Publish and send to the client"):
            self.assertNotIn(never, text, never)
        self.assertIn("/api/publish", page.PAGE.read_text(encoding="utf-8"), "the served page has it")

    def test_row_796_the_published_page_draws_no_publish_box_option_or_heading(self):
        # shell.css is shared, so the published file carries the rules; no element wears them (no #publish-dialog, no .pubopt, no .dlg)
        text = page.VIEW_PAGE.read_text(encoding="utf-8")
        self.assertIsNone(re.search(r'class="[^"]*\b(pubopt|pubopts|dlg)\b', text), "no option or box element in the published page")
        self.assertIsNone(re.search(r'id="(publish-dialog|pub-title)"', text))

    def test_only_publishApi_names_the_three_routes(self):
        for f in PAGE_SRC.rglob("*"):
            if f.is_file() and f.name != "publishApi.js":
                body = f.read_text(encoding="utf-8")
                # "/api/publication" alone: /api/publications is the Published reports list (#443), which only pastReportsApi.js names
                for route in ("/api/publish", "/api/client-folder", "/api/publication"):
                    found = re.search(re.escape(route) + ("(?!s)" if route == "/api/publication" else ""), body)
                    self.assertIsNone(found, f"{f.name} names {route}")
                if f.name != "pastReportsApi.js":
                    for route in ("/api/publications", "/api/past-report"):
                        self.assertNotIn(route, body, f"{f.name} names {route}")

    def test_the_words_in_the_page_are_the_specs(self):
        src = "".join(f.read_text(encoding="utf-8") for f in PAGE_SRC.rglob("edit/*") if f.is_file())
        for key in ("button_local", "button_client", "client_sees"):
            self.assertIn(to_client.MESSAGES[key], src, key)
        # not_saved: the spec's sentence, with its last words now the link "Settings, Publishing" (the prototype's wording, D-14)
        self.assertEqual(to_client.MESSAGES["not_saved"], "No client folder yet. Set it in Settings.")
        self.assertIn("No client folder yet. Set it in ", src)
        self.assertIn('NO_FOLDER_LINK = "Settings, Publishing"', src)
        for label in to_client.MESSAGES["clash_choices"][:3]:
            self.assertIn(label, src)
        self.assertNotRegex(src, r"report editor|(?<!X-)Clark\b")


if __name__ == "__main__":
    unittest.main()
