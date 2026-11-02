"""#437: the Publish words that follow the prototype (system/prototype/io.js), without a browser.

The footer of a published page, the Publish dialog's line about the next number, the second warning sentence, and the finished
state (a tick on the button, the dialog closing, the toast). The page's own behaviour is read in a browser in
tests/test_publish_dialog.py and tests/test_publication_footer.py; here the source of the words is pinned, and the one route
change (GET /api/publication also says the next number) is tested over a real server.

Run: python3 dev/run_tests.py test_publish_words
"""
import unittest

from _paths import SRC
from clark import page, to_client
from test_publish_route import Base

PAGE_SRC = SRC / "clark" / "page" / "src"
PROTOTYPE = (SRC.parent / "system" / "prototype" / "io.js").read_text(encoding="utf-8")
SECOND = "Only what is shown in View mode is included."
WARNING = "The client will see this page. " + SECOND


def src(name):
    return (PAGE_SRC / name).read_text(encoding="utf-8")


class TheFooter(unittest.TestCase):
    """Row 25: "Published <date>. Publication N . <date>. View only." (prototype io.js:266)."""

    def test_the_prototype_says_it_this_way(self):
        self.assertIn("Published ${D.fd(D.TODAY)}. ${opts.n ? 'Publication ' + opts.n + ' · ' + D.fd(D.TODAY) + '. ' : ''}View only.", PROTOTYPE)

    def test_the_page_builds_the_prototype_words(self):
        app = src("components/App.jsx")
        self.assertIn("`Published ${plainDate(asAt.value)}. `", app)
        self.assertIn("Publication {publication.value}", app)
        self.assertIn("` · ${plainDate(asAt.value)}`", app)
        self.assertIn(". View only.</footer>", app, "a file with no date still says it is view only")

    def test_the_published_page_carries_the_words_and_nothing_internal(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        self.assertIn("View only.", view)
        self.assertIn("Published ${", view)
        self.assertNotIn("Only what is shown in View mode", view, "the dialog's words are not in a published file")


class TheDialogLine(unittest.TestCase):
    """Row 26: "this will be Publication N . last published <date>, to the client or locally" (io.js:307)."""

    def test_the_prototype_says_it_this_way(self):
        self.assertIn("this will be Publication ${nextN}${last ? ` · last published ${D.fd(last.at.slice(0, 10))}${last.client ? ', to the client' : ', locally'}` : ''}", PROTOTYPE)

    def test_the_page_builds_the_line_from_the_next_number_and_the_last_publication(self):
        line = src("edit/publishLine.js")
        for part in ("this will be Publication ${next}", "last published ${", ", to the client", ", locally", "week ending"):
            self.assertIn(part, line)
        self.assertIn("dialogLine(", src("edit/Publish.jsx"))

    def test_the_page_asks_again_when_the_dialog_opens(self):
        state = src("edit/publishState.js")
        self.assertRegex(state, r"export function open\(\)[^}]*refreshLatest\(\)")


class TheNextNumber(Base):
    def test_the_latest_answer_also_says_the_next_number_and_nothing_more_internal(self):
        status, got = self.rig.call("GET", "/api/publication?project=PUB")
        self.assertEqual((status, got), (200, {"ok": True, "latest": None, "next": 1}))
        self.rig.publish()
        status, got = self.rig.call("GET", "/api/publication?project=PUB")
        self.assertEqual((status, got["next"], sorted(got)), (200, 2, ["latest", "next", "ok"]))
        self.assertEqual(sorted(got["latest"]), ["at", "to_client"])


class TheWarning(unittest.TestCase):
    """Rows 29 and 56: the second sentence, built once (io.js:313)."""

    def test_the_prototype_says_it_this_way(self):
        self.assertIn(WARNING, PROTOTYPE)

    def test_the_dialog_model_and_the_page_say_it_with_both_sentences(self):
        self.assertEqual(to_client.MESSAGES["client_sees"], WARNING)
        self.assertIn(WARNING, src("edit/Publish.jsx"))
        ticked = to_client.dialog_step(to_client.new_dialog_state("/x/Harbour Bridge"), "tick", True)
        self.assertEqual(to_client.to_client_dialog(ticked)["line"], WARNING)


class TheFinishedState(unittest.TestCase):
    """Rows 27 and 57: a tick and "Published (Publication N)" on the button, the dialog closes by itself, a toast says what was
    done (io.js:333-37). The prototype's Undo is not built: a publication is no step and has none (history.py, #66)."""

    def test_the_prototype_says_it_this_way(self):
        self.assertIn("`${C.icon('check', 's tick')}Published (Publication ${n})`", PROTOTYPE)
        self.assertIn("setTimeout(() => { if (d.open && form.isConnected) d.close(); }, 1200)", PROTOTYPE)

    def test_the_button_shows_the_tick_and_the_number(self):
        jsx = src("edit/Publish.jsx")
        self.assertIn("data-done", jsx)
        self.assertIn("doneWords(", jsx)
        self.assertIn("`Published (Publication ${n})`", src("edit/publishLine.js"))
        self.assertNotIn('"Close"', jsx, "the finished button no longer says Close")

    def test_it_closes_by_itself_and_says_so_in_a_toast(self):
        state = src("edit/publishState.js")
        self.assertIn("1200", state)
        self.assertRegex(state, r"say\(\"done\", said\)")
        self.assertIn("setTimeout(", state)

    def test_no_internal_word_in_the_new_words(self):
        for name in ("edit/publishLine.js",):
            text = src(name).lower()
            for word in ("path", "folder name", "database", "json", "traceback"):
                self.assertNotIn(word, text, f"{name}: {word}")


if __name__ == "__main__":
    unittest.main()
