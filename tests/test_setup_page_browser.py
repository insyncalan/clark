"""#836 step 5: the setup page as drawn, in headless Chrome (src/clark/setup_page.py). Run: python3 dev/run_tests.py test_setup_page_browser
One file at a time under the browser slot, with the stub osascript first on PATH (PATH=/tmp/nodialog:$PATH). A real setup server (SetupRunning, port 0)
over temporary folders; the folder window is always a fake function. Every state: to fix with "Choose a folder", waiting for the folder window,
a refused folder, Cancel, done (every check ready), a page from before a restart. At 360, 900 and 1400 px, light and dark, reduced motion pinned.
Required: fails, never skips, without Chrome."""
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT  # noqa: F401
from test_server import CHROME, chrome, wait
from test_server_setup import SetupRunning

from clark import doctor, platform as pl, server as sv, setup_mode

WIDTHS = (360, 900, 1400)
THEMES = ("light", "dark")

LUMINANCE = """(() => {
  const lum = c => { const [r, g, b] = c.map(v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }); return .2126 * r + .7152 * g + .0722 * b; };
  const rgb = s => (s.match(/[\\d.]+/g) || [0, 0, 0, 0]).map(Number);
  const back = el => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.length < 4 || c[3] > 0) return c.slice(0, 3); } return [255, 255, 255]; };
  const low = [];
  for (const el of document.querySelectorAll('h1, p, .label, .words, button')) {
    if (!el.offsetParent || !el.textContent.trim()) continue;
    const a = lum(rgb(getComputedStyle(el).color).slice(0, 3)), b = lum(back(el));
    const ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
    if (ratio < 4.5) low.push([el.className || el.tagName, el.textContent.slice(0, 30), ratio.toFixed(2)]);
  }
  return low;
})()"""


def check(name, kind, words, required=False):
    """A check of the doctor's shape whose id is `name` (a check's id is its function's name without 'check_')."""
    def run(seen):
        return doctor.Line(kind, words)
    run.__name__ = "check_" + name
    return doctor.Check(f"The {name} check", required, run)


class Page:
    def __init__(self, cdp, sid):
        self.cdp, self.sid = cdp, sid

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, seconds=10):
        if not wait(lambda: self.js(expr), seconds):
            raise AssertionError(f"never true: {what} ({expr})")

    def call(self, method, params=None):
        return self.cdp.call(method, params, self.sid)

    def size(self, width):
        self.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False})

    def look(self, scheme):
        self.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                              {"name": "prefers-reduced-motion", "value": "reduce"}]})

    def click(self, selector):
        x, y = self.js(f"(() => {{ const r = document.querySelector({json.dumps(selector)}).getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }})()")
        for kind in ("mousePressed", "mouseReleased"):
            self.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left", "clickCount": 1})

    def key(self, key, code, vk, text=None):
        for kind in ("keyDown", "keyUp"):
            params = {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk}
            if text and kind == "keyDown":
                params["text"] = text
            self.call("Input.dispatchKeyEvent", params)

    def tab(self):
        self.key("Tab", "Tab", 9)

    def enter(self):
        self.key("Enter", "Enter", 13, "\r")

    def state(self):
        return self.js("document.body.dataset.state")

    def rows(self):
        return self.js("[...document.querySelectorAll('#checks li')].map(li => [li.dataset.id, li.dataset.status, li.querySelector('.label').textContent, li.querySelector('.words').textContent])")

    def shown(self, selector):
        return self.js(f"(() => {{ const e = document.querySelector({json.dumps(selector)}); return !!e && !e.hidden && e.offsetParent !== null; }})()")

    def text(self, selector):
        return self.js(f"document.querySelector({json.dumps(selector)}).textContent")


class Case(unittest.TestCase):
    answer = None
    gate = None

    @classmethod
    def setUpClass(cls):
        assert Path(CHROME).is_file(), f"Chrome is needed for the required browser tests ({CHROME!r}); set CLARK_CHROME"

    def setUp(self):
        self.home = Path(tempfile.mkdtemp(prefix="clark-home-")).resolve()
        self.addCleanup(shutil.rmtree, self.home, True)
        self.default = self.home / "Library" / "Application Support" / "clark"
        self.default.parent.mkdir(parents=True)
        self.onedrive = self.home / "OneDrive - Work"
        self.onedrive.mkdir()
        self.good = self.home / "Elsewhere"
        self.good.mkdir()
        self.asked = []

    def choose(self, prompt):
        self.asked.append(prompt)
        if self.gate is not None:
            self.gate.wait(10)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer

    def serve(self, folder=None, checks=None, **kw):
        folder = folder or self.default
        checks = checks if checks is not None else (doctor.CHECKS[1], doctor.CHECKS[2],
                                                    check("browser", doctor.ADVICE, "Chrome wasn't found, so clark will open in your usual browser. "
                                                          "Install Chrome to give clark its own window."))
        service = setup_mode.Setup(folder, home=self.home, on=pl.MAC, choose_folder=self.choose, onedrive_roots=lambda: [self.onedrive],
                                   environ={}, prompt=setup_mode.FOLDER_PROMPT, checks=checks, **kw)
        s = SetupRunning(service)
        self.addCleanup(s.close)
        return s, service

    def visit(self, cdp, s, until_state=None):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        p = Page(cdp, cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"])
        p.call("Page.enable")
        p.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__errors = []; window.addEventListener('error', e => window.__errors.push(String(e.message)));"
                                                                    "window.addEventListener('unhandledrejection', e => window.__errors.push('rejected'));"
                                                                    "document.addEventListener('securitypolicyviolation', e => window.__errors.push('csp ' + e.violatedDirective));"})
        p.look("light")
        p.size(1400)
        p.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/"})
        p.until("document.body && document.body.dataset.state && document.body.dataset.state !== 'loading'", "the first checks drew")
        if until_state:
            p.until(f"document.body.dataset.state === {json.dumps(until_state)}", until_state)
        return p

    def clean(self, p):
        self.assertEqual(p.js("window.__errors"), [], "no script error and no policy violation")
        self.assertEqual(p.js("document.getAnimations().length"), 0)


class ToFix(Case):
    """Data folder inside OneDrive: the first-run case."""

    def inside(self):
        inside = self.onedrive / "clark"
        return inside

    def test_the_page_says_what_to_fix_and_offers_the_two_buttons(self):
        s, _ = self.serve(self.inside())
        with chrome() as cdp:
            p = self.visit(cdp, s)
            self.assertEqual(p.state(), "fix")
            self.assertEqual(p.js("document.title"), "Setting up clark")
            self.assertEqual(p.text("h1"), "Setting up clark")
            self.assertEqual(p.text(".notice"), "clark is being set up. Nothing is saved until the checks below pass.")
            rows = p.rows()
            self.assertEqual([r[:3] for r in rows], [["data_folder", "ready", "Ready"], ["data_not_in_onedrive", "fix", "To fix"],
                                                     ["browser", "advice", "Worth knowing"]])
            self.assertIn("which is inside OneDrive.", rows[1][3])
            self.assertTrue(rows[1][3].endswith("Backups can still go to OneDrive."))
            self.assertEqual(p.text("#line"), "1 thing to fix before clark can start. Fix it, then choose Check again.")
            self.assertEqual(rows[2][3], "Chrome wasn't found, so clark will open in your usual browser. Install Chrome to open clark there.")
            for gone in ("Terminal", "python3", "start clark again", "double-click", "doctor"):
                self.assertNotIn(gone, p.js("document.body.innerText"))
            self.assertEqual([p.shown("#choose"), p.shown("#again"), p.shown("#status"), p.shown("#problem")], [True, True, False, False])
            self.assertEqual(p.text("#choose"), "Choose a folder")
            self.assertEqual(p.text("#again"), "Check again")
            self.clean(p)

    def test_two_things_to_fix_say_how_many(self):
        checks = (check("data_not_in_onedrive", doctor.FIX, "One.", True), check("port", doctor.FIX, "Two.", True),
                  check("python", doctor.READY, "Three."))
        s, _ = self.serve(checks=checks)
        with chrome() as cdp:
            p = self.visit(cdp, s)
            self.assertEqual(p.text("#line"), "2 things to fix before clark can start. Fix each one, then choose Check again.")

    def test_a_fix_that_a_folder_cannot_mend_has_no_choose_button(self):
        s, _ = self.serve(checks=(check("port", doctor.FIX, "Nothing was started.", True),))
        with chrome() as cdp:
            p = self.visit(cdp, s)
            self.assertFalse(p.shown("#choose"))
            self.assertTrue(p.shown("#again"))

    def test_a_check_that_cannot_run_says_so_and_the_page_waits(self):
        s, _ = self.serve(checks=(check("python", doctor.NOT_CHECKED, "The Python check can't run on this computer yet.", True),))
        with chrome() as cdp:
            p = self.visit(cdp, s)
            self.assertEqual(p.state(), "fix")
            self.assertEqual(p.rows()[0][2], "Not checked")
            self.assertTrue(p.text("#line").startswith("Some checks can't run on this computer yet"))

    def test_the_heartbeat_is_sent(self):
        s, _ = self.serve(self.inside())
        with mock.patch.object(sv, "mark_here") as here:
            with chrome() as cdp:
                self.visit(cdp, s)
                self.assertTrue(wait(lambda: here.called, 5))

    def test_check_again_reads_the_folder_again(self):
        s, service = self.serve(self.inside())
        with chrome() as cdp:
            p = self.visit(cdp, s)
            self.assertEqual(p.rows()[1][1], "fix")
            service.folder = self.good
            p.click("#again")
            p.until("document.body.dataset.state !== 'fix'", "the page moved on")


class Choosing(Case):
    def test_waiting_for_the_folder_window_then_done(self):
        self.answer, self.gate = str(self.good), threading.Event()
        s, service = self.serve(self.onedrive / "clark")
        with chrome() as cdp:
            p = self.visit(cdp, s)
            p.click("#choose")
            p.until("document.body.dataset.state === 'waiting'", "waiting state")
            self.assertEqual(p.text("#status"), "Waiting for you to choose a folder.")
            self.assertEqual(p.js("[document.querySelector('#choose').disabled, document.querySelector('#again').disabled]"), [True, True])
            self.assertEqual(self.asked, ["Choose a folder for your clark data"])
            self.assertEqual(p.js("document.querySelector('#status').getAttribute('role')"), "status")
            self.gate.set()
            p.until("document.body.dataset.state === 'done'", "done state")
            self.assertEqual(p.text("#line"), "Everything clark needs is ready. Opening clark.")
            self.assertFalse(p.shown("#choose"))
            self.assertFalse(p.shown("#status"))
            self.assertEqual(p.js("[...document.querySelectorAll('#checks li')].map(li => li.dataset.status)"), ["ready", "ready", "advice"])
            s.thread.join(10)
            self.assertFalse(s.thread.is_alive(), "the setup server stopped once it said done")
            self.assertEqual(service.folder, self.good)
            self.assertEqual((self.default.parent / setup_mode.POINTER_NAME).read_text(encoding="utf-8"), str(self.good) + "\n")
            self.clean(p)

    def test_cancel_says_nothing_and_changes_nothing(self):
        self.answer = None
        s, service = self.serve(self.onedrive / "clark")
        with chrome() as cdp:
            p = self.visit(cdp, s)
            before = p.rows()
            p.click("#choose")
            p.until("document.body.dataset.state === 'fix' && !document.querySelector('#choose').disabled", "back to fix")
            self.assertEqual(self.asked, [setup_mode.FOLDER_PROMPT])
            self.assertEqual([p.shown("#status"), p.shown("#problem")], [False, False])
            self.assertEqual(p.rows(), before)
            self.assertEqual(p.js("document.activeElement.id"), "choose")
            self.assertFalse((self.default.parent / setup_mode.POINTER_NAME).exists())
            self.clean(p)

    def test_a_folder_inside_onedrive_is_refused_with_the_platforms_words(self):
        inside = self.onedrive / "other"
        inside.mkdir()
        self.answer = str(inside)
        s, _ = self.serve(self.onedrive / "clark")
        with chrome() as cdp:
            p = self.visit(cdp, s)
            p.click("#choose")
            p.until("document.body.dataset.state === 'refused'", "refused state")
            said = p.text("#problem")
            self.assertTrue(said.startswith("Your data can't be kept in "), said)
            self.assertIn("inside OneDrive", said)
            self.assertEqual(p.js("document.querySelector('#problem').getAttribute('role')"), "alert")
            self.assertEqual(p.js("document.activeElement.id"), "choose")
            self.assertEqual(p.js("document.querySelector('#choose').disabled"), False)
            self.assertTrue(p.shown("#choose"))
            p.click("#choose")                       # a second try clears the old reason first
            p.until("document.body.dataset.state === 'refused'", "refused again")
            self.assertEqual(self.asked, [setup_mode.FOLDER_PROMPT] * 2)
            self.clean(p)

    def test_a_folder_that_is_not_there_says_choose_a_different_folder(self):
        self.answer = str(self.home / "gone")
        s, _ = self.serve(self.onedrive / "clark")
        with chrome() as cdp:
            p = self.visit(cdp, s)
            p.click("#choose")
            p.until("document.body.dataset.state === 'refused'", "refused state")
            self.assertEqual(p.text("#problem"), "Your clark data can't be saved in ~/gone. Choose a different folder.")
            self.assertNotIn("start clark again", p.js("document.body.innerText"))

    def test_a_window_that_cannot_open_says_the_platforms_words(self):
        self.answer = pl.PlatformError("The folder window could not be opened. " + pl.TRY_AGAIN)
        s, _ = self.serve(self.onedrive / "clark")
        with chrome() as cdp:
            p = self.visit(cdp, s)
            p.click("#choose")
            p.until("document.body.dataset.state === 'refused'", "refused state")
            self.assertEqual(p.text("#problem"), "The folder window could not be opened. " + pl.TRY_AGAIN)

    def test_the_keyboard_reaches_both_buttons_and_enter_presses_them(self):
        s, service = self.serve(self.onedrive / "clark")
        with chrome() as cdp:
            p = self.visit(cdp, s)
            p.tab()
            self.assertEqual(p.js("document.activeElement.id"), "choose")
            p.tab()
            self.assertEqual(p.js("document.activeElement.id"), "again")
            self.assertEqual(p.js("document.activeElement.matches(':focus-visible')"), True)
            self.assertEqual(p.js("getComputedStyle(document.activeElement).outlineStyle"), "solid")
            self.assertEqual(p.js("parseFloat(getComputedStyle(document.activeElement).outlineWidth)"), 3)
            service.folder = self.good
            p.enter()
            p.until("document.body.dataset.state === 'done'", "Enter on Check again ran the checks and finished")


class AfterRestart(Case):
    def test_a_page_from_before_a_restart_reloads_itself(self):
        s, _ = self.serve(self.onedrive / "clark")
        with chrome() as cdp:
            p = self.visit(cdp, s)
            p.js("window.__old = true; 1")
            new = "n" * len(sv.TOKEN)
            with mock.patch.object(sv, "TOKEN", new):
                p.click("#again")
                p.until("window.__old === undefined && document.body.dataset.state === 'fix'", "the page reloaded")
                self.assertIn(new, p.js("document.getElementById('clark-boot').textContent"))


class Looks(Case):
    """Every state of the look: 360, 900 and 1400 px, light and dark, nothing wider than the window, 44 px buttons, 4.5:1 text."""

    def all_four(self):
        return (check("data_folder", doctor.READY, "Your clark data can be saved in ~/x.", True),
                check("data_not_in_onedrive", doctor.FIX, "Your clark data is set to go in ~/OneDrive - Work/" + "very-long-folder-name-" * 6 +
                      "clark, which is inside OneDrive. OneDrive copies files while they are being written.", True),
                check("browser", doctor.ADVICE, "Chrome wasn't found."), check("claude", doctor.NOT_CHECKED, "Claude Code can't run yet."))

    def test_each_width_and_theme(self):
        s, _ = self.serve(checks=self.all_four())
        with chrome() as cdp:
            p = self.visit(cdp, s)
            for scheme in THEMES:
                p.look(scheme)
                for w in WIDTHS:
                    p.size(w)
                    with self.subTest(scheme=scheme, width=w):
                        self.assertEqual(p.js("window.matchMedia('(prefers-color-scheme: dark)').matches"), scheme == "dark")
                        self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)
                        self.assertEqual(p.js("[...document.querySelectorAll('main, li, .words, button')].filter(e => e.getBoundingClientRect().right > innerWidth + 0.5 "
                                              "|| e.getBoundingClientRect().left < -0.5).length"), 0)
                        self.assertGreaterEqual(p.js("Math.min(...[...document.querySelectorAll('button')].filter(b => b.offsetParent).map(b => b.getBoundingClientRect().height))"), 44)
                        self.assertEqual(p.js(LUMINANCE), [], "text is at least 4.5:1 on its background")
                        self.assertGreaterEqual(p.js("parseFloat(getComputedStyle(document.body).fontSize)"), 15)
                        self.assertGreaterEqual(p.js("Math.min(document.querySelector('h1').getBoundingClientRect().left, innerWidth - document.querySelector('li').getBoundingClientRect().right)"), 16, "a 16 px gutter")
            self.clean(p)

    def test_the_four_labels_are_text_not_only_colour(self):
        s, _ = self.serve(checks=self.all_four())
        with chrome() as cdp:
            p = self.visit(cdp, s)
            self.assertEqual([r[2] for r in p.rows()], ["Ready", "To fix", "Worth knowing", "Not checked"])

    def test_the_done_state_and_the_waiting_state_fit_too(self):
        self.answer, self.gate = str(self.good), threading.Event()
        s, _ = self.serve(self.onedrive / "clark")
        with chrome() as cdp:
            p = self.visit(cdp, s)
            p.click("#choose")
            p.until("document.body.dataset.state === 'waiting'", "waiting")
            for scheme in THEMES:
                p.look(scheme)
                for w in WIDTHS:
                    p.size(w)
                    with self.subTest(state="waiting", scheme=scheme, width=w):
                        self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)
                        self.assertEqual(p.js(LUMINANCE), [])
            self.gate.set()
            p.until("document.body.dataset.state === 'done'", "done")
            for scheme in THEMES:
                p.look(scheme)
                for w in WIDTHS:
                    p.size(w)
                    with self.subTest(state="done", scheme=scheme, width=w):
                        self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w)
                        self.assertEqual(p.js(LUMINANCE), [])


if __name__ == "__main__":
    unittest.main()
