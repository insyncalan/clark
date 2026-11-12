"""#836 (Quit): the Settings card "Quit clark", in a real (headless) Chrome against the real server routes. Run: python3 dev/run_tests.py test_quit_card

What is asserted: the card is on Settings with a chip, a heading and one button, "Quit clark"; one click posts /api/quit once (the server's stop is
recorded, not carried out, so the page stays to be read), the button goes off so a second click does nothing, and the page says
"Stopping clark. You can close this window."; when the server refuses the page shows the server's own plain words, and when
nothing answers it shows "Quitting did not work. Try again." and the button works again. No Export, Save, Publish or Import is pressed.
Chrome is required: these tests fail, never skip, without it.
"""
import tempfile
import unittest

from _real_server import real_server
from clark import page
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

STOPPING = "Stopping clark. You can close this window."
FAILED = "Quitting did not work. Try again."
SAVING = "Finishing your save first. Then clark stops."
PUBLISHING = "Finishing your publish first. Then clark stops."
ASK = "Quit clark now? To start it again, double-click clark.command in the clark folder. With Docker, start it the same way you did before."
AGAIN = "To start clark again, double-click clark.command in the clark folder. With Docker, start it the same way you did before."


class Card(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = real_server(self.store.path, self.store.data_for, projects=lambda archived=False: [{"code": c, "name": c} for c in sorted(self.ids)],
                        page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.stops = []
        s.httpd.shutdown = lambda: self.stops.append(1)            # the stop is watched, not carried out
        self.addCleanup(s.close)
        return s

    def until(self, cdp, sid, expr, what, secs=30):
        self.assertTrue(wait(lambda: bool(cdp.js(f"!!({expr})", sid)), secs), f"timed out waiting for {what}")

    def visit(self, cdp, port, scheme="light", width=1400):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                              {"name": "prefers-reduced-motion", "value": "reduce"}]}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{port}/#settings&p=TUL"}, sid)
        self.until(cdp, sid, "document.querySelector('#quit-h')", "the Quit card")
        self.until(cdp, sid, "document.getAnimations().length === 0", "motion to finish")
        return sid

    def test_the_card_has_a_chip_a_heading_and_one_button(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port)
            self.assertEqual(cdp.js("document.querySelector('#quit-h').textContent", sid), "Quit")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.set-nav .set-chip')].map(c => c.textContent.trim()).includes('Quit')", sid), True)
            self.assertEqual(cdp.js("document.querySelectorAll('#quit button').length", sid), 1)
            self.assertEqual(cdp.js("document.querySelector('#quit button').textContent.trim()", sid), "Quit clark")
            self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)

    def test_one_click_quits_once_and_says_so(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port)
            cdp.js("document.querySelector('#quit button').click()", sid)
            self.until(cdp, sid, f"document.querySelector('#quit').innerText.includes({ASK!r})", "the confirm words")
            self.assertEqual(self.stops, [], "one click only asks")
            self.confirm(cdp, sid)
            self.until(cdp, sid, f"document.querySelector('#quit').innerText.includes({STOPPING!r})", "the stopping line")
            self.assertEqual(cdp.js(f"document.querySelector('#quit').innerText.includes({AGAIN!r})", sid), True)
            self.assertTrue(wait(lambda: len(self.stops) == 1, 10), "the server was told to stop")
            self.assertEqual(cdp.js("[...document.querySelectorAll('#quit button')].every(b => b.disabled)", sid), True)
            cdp.js("document.querySelectorAll('#quit button').forEach(b => b.click())", sid)
            self.assertEqual(len(self.stops), 1, "a second click does nothing")

    def confirm(self, cdp, sid):
        self.until(cdp, sid, "document.querySelector('#quit-yes')", "the confirm button")
        cdp.js("document.querySelector('#quit-yes').click()", sid)

    def test_a_running_save_or_publish_is_said_instead_of_the_idle_line(self):
        """Row 1041: the server says which job it finishes first; the card shows that line (and the idle line only when none runs), at 1400 and 900."""
        s = self.serve()
        for width in (1400, 900):
            for finishing, line in (("save", SAVING), ("publish", PUBLISHING), (None, STOPPING)):
                with chrome() as cdp:
                    sid = self.visit(cdp, s.port, width=width)
                    cdp.js("window.fetch = () => Promise.resolve(new Response(JSON.stringify({ok: true, quit: true, finishing: %s}), {status: 200}))" % ("null" if finishing is None else repr(finishing)), sid)
                    cdp.js("document.querySelector('#quit button').click()", sid)
                    self.confirm(cdp, sid)
                    self.until(cdp, sid, f"document.querySelector('#quit').innerText.includes({line!r})", f"{line} at {width}")
                    text = cdp.js("document.querySelector('#quit').innerText", sid)
                    for other in (SAVING, PUBLISHING, STOPPING):
                        self.assertEqual(other in text, other == line, (width, finishing, other))
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)

    def test_cancel_leaves_clark_running(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port)
            cdp.js("document.querySelector('#quit button').click()", sid)
            self.until(cdp, sid, "document.querySelector('#quit-no')", "the cancel button")
            cdp.js("document.querySelector('#quit-no').click()", sid)
            self.until(cdp, sid, "!document.querySelector('#quit-yes')", "the confirm to close")
            self.assertEqual(cdp.js(f"document.querySelector('#quit').innerText.includes({ASK!r})", sid), False)
            self.assertEqual(cdp.js("document.querySelector('#quit button').textContent.trim()", sid), "Quit clark")
            self.assertEqual(self.stops, [])

    def test_a_refusal_and_no_answer_are_said_plainly_and_can_be_tried_again(self):
        s = self.serve()
        with chrome() as cdp:
            sid = self.visit(cdp, s.port)
            cdp.js("window.fetch = () => Promise.resolve(new Response(JSON.stringify({ok: false, code: 'server_error', message: 'Something went wrong, and nothing was changed. Try again, or restart clark.'}), {status: 500}))", sid)
            cdp.js("document.querySelector('#quit button').click()", sid)
            self.confirm(cdp, sid)
            self.until(cdp, sid, "document.querySelector('#quit').innerText.includes('Something went wrong, and nothing was changed.')", "the server's words")
            self.assertEqual(cdp.js("document.querySelector('#quit button').disabled", sid), False)
            cdp.js("window.fetch = () => Promise.reject(new TypeError('failed'))", sid)
            cdp.js("document.querySelector('#quit button').click()", sid)
            self.confirm(cdp, sid)
            self.until(cdp, sid, f"document.querySelector('#quit').innerText.includes({FAILED!r})", "the fallback words")
            self.assertEqual(cdp.js("document.querySelector('#quit').innerText.includes('TypeError')", sid), False)
            self.assertEqual(cdp.js("document.querySelector('#quit button').disabled", sid), False)
            self.assertEqual(self.stops, [], "neither stopped the server")


if __name__ == "__main__":
    unittest.main()
