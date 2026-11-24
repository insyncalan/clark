"""Row 1435: "Fix it with AI" for a slash-command file that does not read (Settings list, Classic, 1400 and 900; Chrome required: fails, never skips).

Run: python3 dev/run_tests.py test_slash_fix_ai_1435
A file that does not read has its own row with the pill "Needs a fix" and the button "Fix it with AI". Pressing it is local (a fake provider records no call, also with AI
off): the old file is saved first as `<file>.old`, the file is rewritten with the lines the seam `ask_commands.readable_lines` keeps, the row goes back to normal and the toast
says "Fixed: N lines kept, M left out. The old file is kept." with Undo, which puts the old file back byte for byte. What a "line" is is not decided: the seam is faked here and
the real one returns None, which gives "Could not fix the file. The old file is kept." and changes nothing."""
import json
import unittest
from unittest import mock

from _paths import SRC  # noqa: F401
from test_page import navigate
from test_server import chrome
from test_slash_ai_1295 import AiBase
from _editor_checks import for_project

from clark import ask_commands as ac
from clark import ask_commands_service

GOOD = {"name": "monday", "menu": "Monday summary", "text": "Overdue by owner", "scope": "anywhere", "result": "answer"}
KEPT = json.dumps(GOOD, indent=1).splitlines()           # a fake seam keeps these lines: together they read
OLD = b'{"name": "monday", "menu": \n\x00 broken\n'
TOAST = "Fixed: %d lines kept, 2 left out. The old file is kept." % len(KEPT)
FAILED = "Could not fix the file. The old file is kept."
FAKE = mock.patch.object(ac, "readable_lines", lambda path: (KEPT, 2))


class Disk(unittest.TestCase):
    """The logic and the route, without a browser."""
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.d = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.addCleanup(__import__("shutil").rmtree, self.d, True)
        self.svc = ask_commands_service.AskCommandsService(self.d)
        (self.d / "ask-commands").mkdir()
        self.bad = self.d / "ask-commands" / "monday.json"
        self.bad.write_bytes(OLD)

    def fix(self, name="monday.json"):
        return self.svc.change({"scope": "all", "action": "fix", "name": name})

    def test_the_seam_is_not_decided_so_the_fix_fails_and_changes_nothing(self):
        status, body = self.fix()
        self.assertEqual((status, body["ok"], body["message"]), (409, False, FAILED))
        self.assertEqual(self.bad.read_bytes(), OLD)
        self.assertEqual(sorted(p.name for p in self.bad.parent.iterdir()), ["monday.json"])

    def test_a_fix_keeps_the_old_file_first_and_rewrites_with_the_kept_lines(self):
        seen = []
        def seam(path):
            seen.append((path.name, sorted(p.name for p in path.parent.iterdir())))
            return KEPT, 2
        with mock.patch.object(ac, "readable_lines", seam):
            status, body = self.fix()
        self.assertEqual(status, 200)
        self.assertEqual(body["message"], "Fixed: %d lines kept, 2 left out. The old file is kept." % len(KEPT))
        self.assertEqual(body["fixed"], {"kept": len(KEPT), "left_out": 2})
        self.assertEqual(seen, [("monday.json", ["monday.json"])])
        self.assertEqual((self.bad.parent / "monday.json.old").read_bytes(), OLD)
        self.assertEqual(self.bad.read_text(encoding="utf-8"), "\n".join(KEPT) + "\n")
        self.assertEqual(body["damaged"], {"all": [], "project": []})
        self.assertEqual([m["name"] for m in body["all"]], ["monday"])

    def test_undo_puts_the_old_file_back_byte_for_byte_and_drops_the_copy(self):
        with mock.patch.object(ac, "readable_lines", lambda p: (KEPT, 0)):
            self.fix()
        status, body = self.svc.change({"scope": "all", "action": "unfix", "name": "monday.json"})
        self.assertEqual(status, 200)
        self.assertEqual(self.bad.read_bytes(), OLD)
        self.assertFalse((self.bad.parent / "monday.json.old").exists())
        self.assertEqual(body["damaged"]["all"], ["monday.json"])

    def test_a_write_that_fails_leaves_the_file_as_it_was(self):
        with mock.patch.object(ac, "readable_lines", lambda p: (KEPT, 0)), mock.patch.object(ac.os, "replace", side_effect=OSError("disk")):
            status, body = self.fix()
        self.assertEqual((status, body["message"]), (409, FAILED))
        self.assertEqual(self.bad.read_bytes(), OLD)
        self.assertEqual(sorted(p.name for p in self.bad.parent.iterdir()), ["monday.json"])

    def test_only_a_file_that_does_not_read_can_be_fixed(self):
        good = self.d / "ask-commands" / "fine.json"
        good.write_text(json.dumps({**GOOD, "name": "fine"}), encoding="utf-8")
        before = good.read_bytes()
        with mock.patch.object(ac, "readable_lines", lambda p: (KEPT, 0)):
            for name in ("fine.json", "../x.json", "nothing.json", "monday.json.old"):
                self.assertEqual(self.fix(name)[1]["message"], FAILED, name)
        self.assertEqual(good.read_bytes(), before)
        self.assertEqual(self.svc.change({"scope": "all", "action": "unfix", "name": "monday.json"})[1]["message"], FAILED)     # no .old copy: nothing to undo


    def test_a_link_is_not_fixed_and_a_copy_is_not_undone_as_a_file(self):
        other = self.d / "elsewhere.txt"
        other.write_bytes(OLD)
        link = self.d / "ask-commands" / "linked.json"
        link.symlink_to(other)
        with mock.patch.object(ac, "readable_lines", lambda p: (KEPT, 0)):
            self.assertEqual(self.fix("linked.json")[1]["message"], FAILED)
        self.assertEqual((other.read_bytes(), link.is_symlink(), (self.d / "ask-commands" / "linked.json.old").exists()), (OLD, True, False))
        (self.d / "ask-commands" / "monday.json.old").write_bytes(b"copy")
        (self.d / "ask-commands" / "monday.json.old.old").write_bytes(b"copy of a copy")
        self.assertEqual(self.svc.change({"scope": "all", "action": "unfix", "name": "monday.json.old"})[1]["message"], FAILED)
        self.assertEqual((self.d / "ask-commands" / "monday.json.old").read_bytes(), b"copy")


class Fix(AiBase):
    def settings_at(self, cdp, width):
        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.until(js, "!!document.querySelector('[data-ask-tab]')", "the tabs are on the page", 30)
        js("document.querySelector('[data-ask-tab=all]').click()")
        return js

    def damage(self):
        (self.d / "ask-commands").mkdir(exist_ok=True)
        (self.d / "ask-commands" / "monday.json").write_bytes(OLD)
        self.s.httpd.ask_commands.change({"scope": "all", "action": "save", "record": {**GOOD, "name": "other"}})

    def test_an_unreadable_file_shows_needs_a_fix_and_the_button_at_1400_and_900(self):
        self.damage()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                js = self.settings_at(cdp, width)
                self.until(js, "!!document.querySelector('#slash-all [data-slash-damaged]')", "the damaged row")
                row = "#slash-all [data-slash-damaged=\"monday.json\"]"
                self.assertEqual(js(f"document.querySelector('{row} .slash-pill-text').innerText"), "Needs a fix")
                self.assertEqual(js(f"document.querySelector('{row} .slash-pill-icon').getAttribute('aria-hidden')"), "true")
                self.assertEqual(js(f"document.querySelector('{row} [data-slash-fix]').innerText"), "Fix it with AI")
                self.assertEqual(js("document.querySelectorAll('#slash-all [data-slash-damaged]').length"), 1)
                self.assertEqual(js("document.querySelector('#slash-all [data-slash-row=other] [data-slash-fix]')"), None)      # a command that reads has none
                self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True)

    def test_a_damaged_file_is_repaired_and_the_old_copy_exists(self):
        for width in (1400, 900):
            with self.subTest(width=width), FAKE, chrome() as cdp:
                self.damage()
                js = self.settings_at(cdp, width)
                self.until(js, "!!document.querySelector('[data-slash-fix]')", "the button")
                js("document.querySelector('[data-slash-fix]').click()")
                self.until(js, "!!document.querySelector('.toasts .toast-card, .toasts [data-undo]')", "the toast")
                self.until(js, "!document.querySelector('[data-slash-damaged]')", "the row is back to normal")
                self.assertIn(TOAST, js("document.querySelector('.toasts').innerText"))
                self.assertEqual((self.d / "ask-commands" / "monday.json.old").read_bytes(), OLD)
                self.assertEqual(js("document.querySelectorAll('#slash-all [data-slash-row=monday]').length"), 1)
                self.assertEqual(js("document.querySelectorAll('.slash-pill').length"), 0)
                (self.d / "ask-commands" / "monday.json.old").unlink()

    def test_undo_restores_the_old_file_byte_for_byte(self):
        with FAKE, chrome() as cdp:
            self.damage()
            js = self.settings_at(cdp, 1400)
            self.until(js, "!!document.querySelector('[data-slash-fix]')", "the button")
            js("document.querySelector('[data-slash-fix]').click()")
            self.until(js, "!!document.querySelector('.toasts [data-undo]')", "Undo")
            self.assertNotEqual((self.d / "ask-commands" / "monday.json").read_bytes(), OLD)
            js("document.querySelector('.toasts [data-undo]').click()")
            self.until(js, "!!document.querySelector('[data-slash-damaged]')", "the pill is back")
            self.assertEqual((self.d / "ask-commands" / "monday.json").read_bytes(), OLD)

    def test_a_failed_fix_has_its_line_and_changes_nothing(self):
        self.damage()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:         # the real seam is not decided: it returns None
                js = self.settings_at(cdp, width)
                self.until(js, "!!document.querySelector('[data-slash-fix]')", "the button")
                js("document.querySelector('[data-slash-fix]').click()")
                self.until(js, "document.querySelector('.toasts').innerText.includes('Could not fix')", "the failed line")
                self.assertIn(FAILED, js("document.querySelector('.toasts').innerText"))
                self.assertEqual((self.d / "ask-commands" / "monday.json").read_bytes(), OLD)
                self.assertEqual(js("!!document.querySelector('[data-slash-damaged]')"), True)
                self.assertEqual(js("!!document.querySelector('.toasts [data-undo]')"), False)

    def test_the_button_works_with_the_ai_switch_off(self):
        self.s.httpd.app_settings.change_ask({"enabled": False})
        with FAKE, chrome() as cdp:
            self.damage()
            js = self.settings_at(cdp, 1400)
            self.until(js, "!!document.querySelector('[data-slash-fix]')", "the button")
            self.assertEqual(js("document.querySelector('[data-slash-fix]').disabled"), False)
            js("document.querySelector('[data-slash-fix]').click()")
            self.until(js, "!document.querySelector('[data-slash-damaged]')", "fixed")
            self.assertEqual(len(self.provider.requests), 0)


class Seam(unittest.TestCase):
    def test_the_seam_is_in_ask_commands_and_is_not_decided_yet(self):
        self.assertIsNone(ac.readable_lines("nothing"))


if __name__ == "__main__":
    unittest.main()
