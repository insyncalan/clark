"""item 836: the Gatekeeper help on the setup page (clark.app is not signed or notarised, so a Mac asks the person to allow it once).
Run: python3 dev/run_tests.py test_setup_page_gatekeeper
The words are PROPOSED and await the owner's approval (~/dev.env/comms/PLAN-106/836-gatekeeper-strings.md); this test pins them so a change is deliberate.
Static: no browser, no server."""
import re
import unittest
from pathlib import Path
from unittest import mock

from clark import platform, setup_mode, setup_page

PROPOSED = {
    "head": "If your Mac won't open clark",
    "why": "Apple has not checked clark, so your Mac asks you to allow it the first time. This is expected.",
    "step_open": "Right click clark, choose Open, then choose Open again in the window that appears.",
    "step_settings": ("If there is no Open button, open System Settings, choose Privacy and Security, find the message about clark "
                      "and choose Open Anyway."),
}
NOT_ON_A_PAGE = ("Terminal", "python3", "bash", "double-click", "doctor", "xcode", "./", " --", "Run ", "drag", "Return", "notaris",
                 "Gatekeeper", "developer id")


class Words(unittest.TestCase):
    def test_the_proposed_words_are_pinned_exactly(self):
        self.assertEqual(setup_page.GATEKEEPER, PROPOSED)

    def test_no_dash_no_terminal_step_no_jargon(self):
        for key, text in setup_page.GATEKEEPER.items():
            with self.subTest(key=key):
                for bad in NOT_ON_A_PAGE + ("–", "—", " - "):
                    self.assertNotIn(bad, text)


class Page(unittest.TestCase):
    def setUp(self):
        self.page = setup_page.html(on=platform.MAC)
        self.shown = re.sub(r"<script.*?</script>|<style.*?</style>", "", self.page, flags=re.S)

    def test_every_line_is_in_the_page_itself_not_only_drawn_by_the_script(self):
        for key, text in setup_page.GATEKEEPER.items():
            with self.subTest(key=key):
                self.assertIn(text, self.shown)

    def test_the_help_is_always_visible_and_after_the_buttons(self):
        m = re.search(r'<section id="gatekeeper"([^>]*)>', self.shown)
        self.assertIsNotNone(m)
        self.assertNotIn("hidden", m.group(1))
        self.assertGreater(m.start(), self.shown.index('id="again"'))

    def test_the_steps_are_a_list_in_order(self):
        steps = re.findall(r"<li>(.*?)</li>", self.shown.split('id="gatekeeper"', 1)[1], flags=re.S)
        self.assertEqual(steps, [PROPOSED["step_open"], PROPOSED["step_settings"]])

    def test_the_old_page_words_are_untouched(self):
        for text in setup_page.WORDS.values():
            self.assertIn(text.split("{n}")[0], self.page)


class OnlyOnAMac(unittest.TestCase):
    """The help is for the Mac's own prompt, so it is not on the page on Windows, Linux or in Docker."""
    def shown(self, page):
        return re.sub(r"<script.*?</script>|<style.*?</style>", "", page, flags=re.S)

    def test_shown_on_a_mac(self):
        page = setup_page.html(on=platform.MAC)
        self.assertIn('id="gatekeeper"', self.shown(page))

    def test_not_shown_on_windows_or_linux(self):
        for system in (platform.WINDOWS, "linux"):
            with self.subTest(system=system):
                shown = self.shown(setup_page.html(on=system))
                self.assertNotIn('id="gatekeeper"', shown)
                for text in setup_page.GATEKEEPER.values():
                    self.assertNotIn(text, shown)

    def test_not_shown_in_docker_even_when_the_system_says_darwin(self):
        with mock.patch.object(platform, "container_mode", return_value=True):
            self.assertNotIn('id="gatekeeper"', self.shown(setup_page.html(on=platform.MAC)))

    def test_the_default_is_this_computer(self):
        for system, wanted in ((platform.MAC, True), (platform.WINDOWS, False), ("linux", False)):
            with self.subTest(system=system), mock.patch.object(platform, "system", return_value=system), \
                    mock.patch.object(platform, "container_mode", return_value=False):
                self.assertEqual('id="gatekeeper"' in self.shown(setup_page.html()), wanted)

    def test_the_page_the_setup_service_sends_follows_its_system(self):
        for system, wanted in ((platform.MAC, True), (platform.WINDOWS, False), ("linux", False)):
            with self.subTest(system=system):
                setup = setup_mode.Setup(Path("/nowhere/data"), home=Path("/nowhere"), on=system)
                self.assertEqual('id="gatekeeper"' in self.shown(setup.page_html()), wanted)


if __name__ == "__main__":
    unittest.main()
