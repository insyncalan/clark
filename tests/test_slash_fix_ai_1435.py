"""Row 1435: "Fix it with AI" for a slash-command file that does not read (Settings list, Classic, 1400 and 900; Chrome required: fails, never skips).

Run: python3 dev/run_tests.py test_slash_fix_ai_1435
A file that does not read has its own row with the pill "Needs a fix" and the button "Fix it with AI". Pressing it is local (a fake provider records no call, also with AI
off): the old file is saved first as `<file>.old`, the file is rewritten with the lines the real reader `ask_commands.readable_lines` keeps (each field of the JSON that passes the checks of read()), the row goes back to normal and the toast
says "Fixed: N lines kept, M left out. The old file is kept." with Undo, which puts the old file back byte for byte. The copy is `<name>.old` (cmd.json becomes cmd.old). A file that is not JSON
at all gives "Could not fix the file. The old file is kept." and changes nothing."""
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
# a file that does not read because "replaces" names another command; it has one unknown field too: 5 fields are kept, 2 left out
OLD = json.dumps({**GOOD, "replaces": "check", "junk": 1}, indent=1).encode("utf-8")
GARBAGE = b'{"name": "monday", "menu": \n\x00 broken\n'
TOAST = "Fixed: 5 lines kept, 2 left out. The old file is kept."
FAILED = "Could not fix the file. The old file is kept."
KEPT = ['"%s": %s' % (k, json.dumps(v)) for k, v in GOOD.items()]


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

    def old(self):
        return sorted(p.name for p in self.bad.parent.iterdir())

    def test_garbage_that_is_not_json_fails_and_changes_nothing(self):
        self.bad.write_bytes(GARBAGE)
        status, body = self.fix()
        self.assertEqual((status, body["ok"], body["message"]), (409, False, FAILED))
        self.assertEqual(self.bad.read_bytes(), GARBAGE)
        self.assertEqual(self.old(), ["monday.json"])

    def test_the_real_reader_keeps_what_passes_the_checks_of_read_and_counts_the_rest(self):
        mixed = {"name": "monday", "menu": "", "text": "x" * (ac.TEXT_MAX + 1), "scope": "nowhere", "result": "draft", "ai": True, "junk": 1}
        self.bad.write_text(json.dumps(mixed), encoding="utf-8")
        self.assertEqual(ac.readable_lines(self.bad), (['"name": "monday"', '"result": "draft"', '"ai": true'], 4))
        self.bad.write_text(json.dumps({**GOOD, "menu": "m" * (ac.MENU_MAX + 1), "text": "  ", "result": "nothing"}), encoding="utf-8")
        self.assertEqual(ac.readable_lines(self.bad), (['"name": "monday"', '"scope": "anywhere"'], 3))
        self.bad.write_text(json.dumps({**GOOD, "name": "other"}), encoding="utf-8")                  # the name is not the file's
        self.assertEqual(ac.readable_lines(self.bad)[1], 1)
        self.bad.write_text(json.dumps({**GOOD, "name": "check", "replaces": "check"}), encoding="utf-8")
        self.assertEqual(ac.readable_lines(self.bad)[1], 1)                                         
        self.bad.write_text(json.dumps({**GOOD, "name": "monday", "replaces": "check"}), encoding="utf-8")
        self.assertEqual(ac.readable_lines(self.bad)[1], 1)                                           # replaces names another command
        locked = self.bad.parent / "history.json"
        locked.write_text(json.dumps({**GOOD, "name": "history", "replaces": "history"}), encoding="utf-8")
        self.assertEqual(ac.readable_lines(locked)[1], 1)                                             # a locked built-in cannot be replaced
        link = self.bad.parent / "link.json"
        link.symlink_to(locked)
        self.assertIsNone(ac.readable_lines(link))
        self.bad.write_text("[1, 2]", encoding="utf-8")
        self.assertEqual(ac.readable_lines(self.bad), ([], 1))
        self.bad.write_text(json.dumps(GOOD), encoding="utf-8")
        self.assertEqual(ac.readable_lines(self.bad), (KEPT, 0))                                      # valid JSON that reads is not None
        self.bad.write_bytes(b"[" + b"1," * ac.FILE_LIMIT + b"1]")                                    # too big to be one of ours: not read
        self.assertIsNone(ac.readable_lines(self.bad))
        self.bad.write_bytes(b"\xff\xfe not text")
        self.assertIsNone(ac.readable_lines(self.bad))

    def test_a_fix_keeps_the_old_file_first_as_name_old_and_rewrites_with_the_kept_lines(self):
        seen = []
        real = ac.readable_lines
        def seam(path):
            seen.append(self.old())
            return real(path)
        with mock.patch.object(ac, "readable_lines", seam):
            status, body = self.fix()
        self.assertEqual(status, 200)
        self.assertEqual(body["message"], TOAST)
        self.assertEqual(body["fixed"], {"kept": 5, "left_out": 2})
        self.assertEqual(seen, [["monday.json"]])
        self.assertEqual(self.old(), ["monday.json", "monday.old"])                                    # cmd.json becomes cmd.old
        self.assertEqual((self.bad.parent / "monday.old").read_bytes(), OLD)
        self.assertEqual([p.name for p in self.bad.parent.glob("*.json")], ["monday.json"])           # the copy never matches the glob of read()
        self.assertEqual(json.loads(self.bad.read_text(encoding="utf-8")), GOOD)
        self.assertEqual(body["damaged"], {"all": [], "project": []})
        self.assertEqual([m["name"] for m in body["all"]], ["monday"])

    def test_a_file_with_nothing_readable_becomes_an_empty_object(self):
        self.bad.write_text(json.dumps({"scope": "nowhere"}), encoding="utf-8")
        status, body = self.fix()
        self.assertEqual((status, body["fixed"]), (200, {"kept": 0, "left_out": 1}))
        self.assertEqual(self.bad.read_text(encoding="utf-8"), "{}\n")

    def test_a_field_that_does_not_read_is_left_out_and_the_file_may_still_need_a_fix(self):
        self.bad.write_text(json.dumps({**GOOD, "scope": "nowhere"}), encoding="utf-8")
        status, body = self.fix()
        self.assertEqual((status, body["fixed"]), (200, {"kept": 4, "left_out": 1}))
        self.assertEqual(body["damaged"]["all"], ["monday.json"])

    def test_a_second_press_of_fix_never_overwrites_the_kept_original(self):
        self.bad.write_text(json.dumps({**GOOD, "scope": "nowhere"}), encoding="utf-8")
        original = self.bad.read_bytes()
        self.assertEqual(self.fix()[0], 200)
        after_first = self.bad.read_bytes()
        status, body = self.fix()                              # the file still needs a fix: pressed again
        self.assertEqual((status, body["ok"], body["message"]), (409, False, FAILED))
        self.assertEqual((self.bad.parent / "monday.old").read_bytes(), original, "the kept original is the person's file, not the first fix")
        self.assertEqual(self.bad.read_bytes(), after_first)

    def test_undo_puts_the_old_file_back_byte_for_byte_and_drops_the_copy(self):
        self.fix()
        status, body = self.svc.change({"scope": "all", "action": "unfix", "name": "monday.json"})
        self.assertEqual(status, 200)
        self.assertEqual(self.bad.read_bytes(), OLD)
        self.assertEqual(self.old(), ["monday.json"])
        self.assertEqual(body["damaged"]["all"], ["monday.json"])

    def test_a_write_that_fails_leaves_the_file_as_it_was(self):
        with mock.patch.object(ac.os, "replace", side_effect=OSError("disk")):
            status, body = self.fix()
        self.assertEqual((status, body["message"]), (409, FAILED))
        self.assertEqual(self.bad.read_bytes(), OLD)
        self.assertEqual(self.old(), ["monday.json"])

    def test_the_seam_can_be_replaced_and_none_gives_the_failed_line(self):
        with mock.patch.object(ac, "readable_lines", lambda p: None):
            self.assertEqual(self.fix()[1]["message"], FAILED)
        self.assertEqual(self.bad.read_bytes(), OLD)

    def test_only_a_file_that_does_not_read_can_be_fixed(self):
        good = self.d / "ask-commands" / "fine.json"
        good.write_text(json.dumps({**GOOD, "name": "fine"}), encoding="utf-8")
        before = good.read_bytes()
        for name in ("fine.json", "../x.json", "nothing.json", "monday.old"):
            self.assertEqual(self.fix(name)[1]["message"], FAILED, name)
        self.assertEqual(good.read_bytes(), before)
        self.assertEqual(self.svc.change({"scope": "all", "action": "unfix", "name": "monday.json"})[1]["message"], FAILED)     # no .old copy: nothing to undo

    def test_a_link_is_not_fixed_and_a_copy_is_not_undone_as_a_file(self):
        other = self.d / "elsewhere.txt"
        other.write_bytes(OLD)
        link = self.d / "ask-commands" / "linked.json"
        link.symlink_to(other)
        self.assertEqual(self.fix("linked.json")[1]["message"], FAILED)
        with mock.patch.object(ac, "readable_lines", lambda p: (KEPT, 0)):                           # even when a reader would keep lines
            self.assertEqual(self.fix("linked.json")[1]["message"], FAILED)
        self.assertEqual((other.read_bytes(), link.is_symlink(), (self.d / "ask-commands" / "linked.old").exists()), (OLD, True, False))
        (self.d / "ask-commands" / "monday.old").write_bytes(b"copy")
        self.assertEqual(self.svc.change({"scope": "all", "action": "unfix", "name": "monday.old"})[1]["message"], FAILED)
        self.assertEqual((self.d / "ask-commands" / "monday.old").read_bytes(), b"copy")


class Fix(AiBase):
    def settings_at(self, cdp, width):
        sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        js = lambda e: cdp.js(e, sid)          # noqa: E731
        self.until(js, "!!document.querySelector('[data-ask-tab]')", "the tabs are on the page", 30)
        js("document.querySelector('[data-ask-tab=all]').click()")
        return js

    def damage(self, content=OLD):
        (self.d / "ask-commands").mkdir(exist_ok=True)
        (self.d / "ask-commands" / "monday.json").write_bytes(content)
        (self.d / "ask-commands" / "monday.old").unlink(missing_ok=True)      # a second pass in one test starts with no kept copy
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
            with self.subTest(width=width), chrome() as cdp:
                self.damage()
                js = self.settings_at(cdp, width)
                self.until(js, "!!document.querySelector('[data-slash-fix]')", "the button")
                js("document.querySelector('[data-slash-fix]').click()")
                self.until(js, "!!document.querySelector('.toasts .toast-card, .toasts [data-undo]')", "the toast")
                self.until(js, "!document.querySelector('[data-slash-damaged]')", "the row is back to normal")
                self.assertIn(TOAST, js("document.querySelector('.toasts').innerText"))
                self.assertEqual((self.d / "ask-commands" / "monday.old").read_bytes(), OLD)
                self.assertEqual(js("document.querySelectorAll('#slash-all [data-slash-row=monday]').length"), 1)
                self.assertEqual(js("document.querySelectorAll('.slash-pill').length"), 0)
                (self.d / "ask-commands" / "monday.old").unlink()

    def test_undo_restores_the_old_file_byte_for_byte(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.damage()
                js = self.settings_at(cdp, width)
                self.until(js, "!!document.querySelector('[data-slash-fix]')", "the button")
                js("document.querySelector('[data-slash-fix]').click()")
                self.until(js, "!!document.querySelector('.toasts [data-undo]')", "Undo")
                self.assertNotEqual((self.d / "ask-commands" / "monday.json").read_bytes(), OLD)
                js("document.querySelector('.toasts [data-undo]').click()")
                self.until(js, "!!document.querySelector('[data-slash-damaged]')", "the pill is back")
                self.assertEqual((self.d / "ask-commands" / "monday.json").read_bytes(), OLD)

    def test_a_failed_fix_has_its_line_and_changes_nothing(self):
        self.damage(GARBAGE)
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:         # not JSON at all: the reader returns None
                js = self.settings_at(cdp, width)
                self.until(js, "!!document.querySelector('[data-slash-fix]')", "the button")
                js("document.querySelector('[data-slash-fix]').click()")
                self.until(js, "document.querySelector('.toasts').innerText.includes('Could not fix')", "the failed line")
                self.assertIn(FAILED, js("document.querySelector('.toasts').innerText"))
                self.assertEqual((self.d / "ask-commands" / "monday.json").read_bytes(), GARBAGE)
                self.assertEqual(js("!!document.querySelector('[data-slash-damaged]')"), True)
                self.assertEqual(js("!!document.querySelector('.toasts [data-undo]')"), False)

    def test_the_button_works_with_the_ai_switch_off(self):
        self.s.httpd.app_settings.change_ask({"enabled": False})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.damage()
                js = self.settings_at(cdp, width)
                self.until(js, "!!document.querySelector('[data-slash-fix]')", "the button")
                self.assertEqual(js("document.querySelector('[data-slash-fix]').disabled"), False)
                js("document.querySelector('[data-slash-fix]').click()")
                self.until(js, "!document.querySelector('[data-slash-damaged]')", "fixed")
                self.assertEqual(len(self.provider.requests), 0)


if __name__ == "__main__":
    unittest.main()
