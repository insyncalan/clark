"""Row 1297, layout of the ruled note in a real browser at 1400 and 900 px: after a failed open the note sits under the Open in your mail app
button and inside the window, in the Draft email editor. Reuses the browser harness of that page."""
import json
import unittest

import test_draft_email_editor as DE
from test_server import chrome  # noqa: F401  (the harness: this file drives Chrome through the base classes above, so the tier reader sees it)

LINK = {"draft": ".pk-foot a"}


class Layout:
    which = ""

    def fail_open(self):
        self.js("window.fetch = () => Promise.resolve(new Response(JSON.stringify({ok: false, message: 'x'}), {status: 503}));")
        self.click(LINK[self.which])

    def check(self, width):
        self.fail_open()
        got = self.val("(function(){ var l = document.querySelector(%s).getBoundingClientRect(), n = document.querySelector('[data-mail-note]'), r = n && n.getBoundingClientRect();"
                       " return r ? {linkBottom: l.bottom, linkLeft: l.left, top: r.top, left: r.left, right: r.right, width: r.width, height: r.height, win: window.innerWidth,"
                       " scroll: document.documentElement.scrollWidth} : null; })()" % json.dumps(LINK[self.which]))
        self.assertIsNotNone(got, "the note is shown after a failed open")
        self.assertEqual(got["win"], width)
        self.assertGreater(got["height"], 0)
        self.assertGreaterEqual(got["top"], got["linkBottom"] - 0.5, f"the note sits under the button at {width}")
        self.assertGreaterEqual(got["left"], 0, f"the note starts inside the window at {width}")
        self.assertLessEqual(got["right"], got["win"], f"the note ends inside the window at {width}")
        self.assertLessEqual(got["scroll"], got["win"], f"no sideways scroll at {width}")


class Draft(Layout, DE.InBrowser):
    which = "draft"

    def test_the_note_sits_under_the_button_and_inside_the_window(self):
        for width in (1400, 900):
            with self.subTest(width=width):
                self.load(width)
                self.mount()
                self.check(width)


if __name__ == "__main__":
    unittest.main()
