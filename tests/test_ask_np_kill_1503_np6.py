"""Row 1503, slice 6: the project's own asking draws nothing at all when its value was not read.

Run: python3 dev/run_tests.py test_ask_np_kill_1503_np6
Settings, Classic, 1400. Chrome is required."""
import unittest

from ask_np_settings_base_1503 import SettingsBase
from test_server import chrome, wait


class AskHereUnread(SettingsBase):
    def test_a_project_value_that_was_not_read_leaves_no_trace_in_the_tab(self):
        """The read for the project's own value fails: no button, no line, and not even an empty box where it would be; the row of the switch is followed by the words' place."""
        real = self.svc.read_new
        self.svc.read_new = lambda project=None: (500, {"ok": False}) if project else real(project)
        self.addCleanup(setattr, self.svc, "read_new", real)
        with chrome() as cdp:
            self.sid = __import__("test_page").navigate(cdp, self.s.port, "#settings&p=ABC&s=claude")
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.until(js, "!!document.querySelector('#ask-settings .pub-msg')", "the project's tab")
            self.assertFalse(wait(lambda: js("!!document.querySelector('[data-ask-here], #ask-new-here')"), 3), "no button and no box for the project's own asking")
            self.assertEqual(js("document.querySelector('#ask-settings > .row').nextElementSibling.className"), "pub-msg", "nothing sits between the switch row and the words' place")


if __name__ == "__main__":
    unittest.main()
