"""The Backups "Copy my backups to" box keeps the keyboard's place in real Chrome.

Run: python3 dev/run_tests.py test_backup_copy_focus
The real Settings page over a stand-in server, with the two backup routes answered by the page's own fetch (a listing, then a slow "saved").
The box saves on Enter or when left (row 1115 S5, no Save button) and keeps focus after Enter in it; the suggestion saves at once. Chrome is required.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import page, server as sv  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
STUB = r"""(() => {
  const real = window.fetch.bind(window);
  const reply = (b) => new Response(JSON.stringify(b), { status: 200, headers: { "Content-Type": "application/json" } });
  window.fetch = (url, opts) => {
    if (String(url).startsWith("/api/backups/copy-folder")) {
      const folder = JSON.parse(opts.body).folder;
      return new Promise((ok) => setTimeout(() => ok(reply({ ok: true, folder, message: "Saved." })), 300));
    }
    if (String(url).startsWith("/api/backups/preview")) return Promise.resolve(reply({ ok: true, when: "today", copy: { projects: 1, work_items: 2, milestones: 3 }, now: null, older: false, same_database: true, last_step: 1 }));
    if (String(url).startsWith("/api/backups/restore")) return new Promise((ok) => setTimeout(() => ok(reply({ ok: false, message: "No." })), 600));
    if (String(url).startsWith("/api/backups")) return Promise.resolve(reply({ ok: true, backups: [{ name: "b1", when: "today", kind_label: "Daily", size_text: "1 KB" }], status: "Fine.", newest_ok: true, keep: 5, keep_label: "Kept", keep_help: "h",
      copy_folder: "", copy_label: "Copy my backups to", copy_help: "Help.", copy_suggestions: ["/tmp/OneDrive"] }));
    return real(url, opts);
  };
})()"""
ACTIVE = "(document.activeElement.matches('[data-copy-folder]') ? 'box' : document.activeElement.tagName)"


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


def key(cdp, sid, k, code, vk, text=None):
    d = {"key": k, "code": code, "windowsVirtualKeyCode": vk}
    cdp.call("Input.dispatchKeyEvent", dict(d, type="keyDown", **({"text": text} if text else {})), sid)
    cdp.call("Input.dispatchKeyEvent", dict(d, type="keyUp"), sid)


class BackupCopyFocus(unittest.TestCase):
    def setUp(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.s = Running(data_for=lambda code, archived=None: self.store.data_for(code), projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}],
                         page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def shown(self, cdp, width=1400):
        sid = page_target(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#settings"}, sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-copy-folder]')", sid)), "the box is on the page")
        return sid

    def test_there_is_no_save_button_and_enter_in_the_box_keeps_focus_in_the_box(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.shown(cdp, width)
                self.assertFalse(cdp.js("!!document.querySelector('[data-copy-save]')", sid), "no Save button (row 1115 S5)")
                cdp.js("document.querySelector('[data-copy-folder]').focus()", sid)
                cdp.js("(() => { const b = document.querySelector('[data-copy-folder]'); b.value = '/tmp/x'; b.dispatchEvent(new Event('input', {bubbles: true})); })()", sid)
                key(cdp, sid, "Enter", "Enter", 13, "\r")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#safety-copy-said p')", sid)), "the answer came")
                self.assertEqual(cdp.js(ACTIVE, sid), "box")

    def test_the_suggestion_saves_at_once_and_is_aria_disabled_and_dimmed_while_busy(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.shown(cdp, width)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-copy-suggestion]')", sid)), "the suggestion is drawn")
                cdp.js("document.querySelector('[data-copy-suggestion]').click()", sid)
                sel = "[data-copy-suggestion]"
                self.assertTrue(wait(lambda: cdp.js(f"document.querySelector('{sel}').getAttribute('aria-disabled') === 'true'", sid)), "aria-disabled while it works")
                self.assertFalse(cdp.js(f"document.querySelector('{sel}').disabled", sid), "not disabled (the focus stays)")
                self.assertLess(float(cdp.js(f"getComputedStyle(document.querySelector('{sel}')).opacity", sid)), 1, "dimmed")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#safety-copy-said p')", sid)), "the answer came")
                self.assertEqual(cdp.js("document.querySelector('[data-copy-folder]').value", sid), "/tmp/OneDrive", "the suggestion was saved")
                self.assertTrue(cdp.js("!document.querySelector('[data-copy-suggestion]').hasAttribute('aria-disabled')", sid), "back to normal")

    def test_esc_while_the_panel_is_busy_does_nothing(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.shown(cdp, width)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-restore]')", sid)), "the backup is drawn")
                cdp.js("document.querySelector('[data-restore]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-put-back]')", sid)), "the confirm step is shown")
                cdp.js("document.querySelector('[data-put-back]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('[data-cancel]').disabled", sid)), "busy: the restore is running")
                cdp.js("document.querySelector('#backup-panel').focus()", sid)
                key(cdp, sid, "Escape", "Escape", 27)
                self.assertTrue(cdp.js("!!document.querySelector('#backup-panel')", sid), "Esc while busy leaves the panel open")
                self.assertTrue(wait(lambda: cdp.js("!document.querySelector('#backup-panel')", sid)), "the refusal closes it once the answer comes")


if __name__ == "__main__":
    unittest.main()
