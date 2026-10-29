"""

Run: python3 dev/run_tests.py test_page_words
The real page runs in headless Chrome against a real server whose data_for is a fake that fails on demand (a KeyError, no
answer for the project, a connection that drops), or whose token check is made to refuse (a wrong token). Each case shows the
exact plain wording and never a Python class name, "JSON", "Not allowed", "Bad request" or "report editor"; "Try again" brings
the page back when the fake does. The server's own messages are #33's file: the page must be safe whatever they say.
"""
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC

from clark import page, server as sv  # noqa: E402
from test_page import DATA, navigate  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

READ_FAILED = "clark could not read this project. Reload the page. If it happens again, restart clark."
HIT_PROBLEM = "clark hit a problem reading this project. Reload the page. If it happens again, restart clark."
NOT_ACCEPTED = "clark did not accept that request. Reload the page."
STALE = "clark was restarted after you opened this page. Reload the page and try again."
NOT_ANSWERING = "clark is not answering. Check that its window is still open, then reload the page."
WENT_WRONG = "Something went wrong"
NEVER = re.compile(r"\w*(Error|Exception)\b|Traceback|JSON|Not allowed|Bad request|[Rr]eport editor|\bClark\b|\bUC\b|!")
PAGE_SRC = Path(page.PAGE).parent / "src"
WAIT = 30     # seconds to poll for what the page should show: a busy machine can take far longer than a quiet one


class Fake:
    """A data_for that can be told to fail: ok, keyerror, none, drop (the connection ends without a reply), wait."""

    def __init__(self):
        self.mode = "ok"
        self.release = threading.Event()

    def __call__(self, code):
        if self.mode == "keyerror":
            raise KeyError("secret/path/name")
        if self.mode == "none":
            return None
        if self.mode == "drop":
            raise ConnectionResetError()
        if self.mode == "wait":
            self.release.wait(WAIT)
        return DATA.get(code)


def lines(cdp, sid):
    """The visible text of the page's main area, as its non-empty lines."""
    text = cdp.js("document.querySelector('main').innerText", sid) or ""
    return [x.strip() for x in text.splitlines() if x.strip()]


class Words(unittest.TestCase):
    def setUp(self):
        self.fake = Fake()
        self.s = Running(data_for=self.fake, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)   # the server logs a fault on purpose
        quiet.start()
        self.addCleanup(quiet.stop)

    def visit(self, cdp, hash_="#dashboard&p=ABC"):
        return navigate(cdp, self.s.port, hash_)

    def shown(self, cdp, sid, expected):
        self.assertTrue(wait(lambda: lines(cdp, sid) == expected, WAIT), f"wanted {expected}, the page shows {lines(cdp, sid)}")
        self.assertIsNone(NEVER.search(" ".join(lines(cdp, sid))), lines(cdp, sid))

    def recovers(self, cdp, sid):
        self.fake.mode = "ok"
        cdp.js("document.querySelector('.again').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1') && document.querySelector('h1').textContent", sid)
                             == "Example Programme", WAIT), "Try again brought the report back")

    def test_a_fault_in_the_data_shows_no_error_name_and_try_again_recovers(self):
        self.fake.mode = "keyerror"
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.shown(cdp, sid, [WENT_WRONG, HIT_PROBLEM, "Try again"])
            self.recovers(cdp, sid)

    def test_a_project_that_is_not_there_says_so_and_what_to_check(self):
        self.fake.mode = "none"
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.shown(cdp, sid, ["That project isn't here", "There is no project with that code. Check the code in the address, or choose a project from the list."])

    def test_a_connection_that_ends_without_a_reply_says_clark_is_not_answering(self):
        self.fake.mode = "drop"
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.shown(cdp, sid, [WENT_WRONG, NOT_ANSWERING, "Try again"])
            self.recovers(cdp, sid)

    def test_a_server_that_is_stopped_says_clark_is_not_answering_and_try_again_works_when_it_is_back(self):
        port = self.s.port

        def page_then_stop():
            """Serves the page, then clark's window closes: the page's own request for the data finds nobody."""
            threading.Thread(target=lambda: (self.s.httpd.shutdown(), self.s.httpd.server_close()), daemon=True).start()
            time.sleep(0.5)
            return page.page_html(tempfile.mkdtemp())
        self.s.httpd.page_html = page_then_stop
        with chrome() as cdp:
            sid = navigate(cdp, port, "#dashboard&p=ABC")
            self.shown(cdp, sid, [WENT_WRONG, NOT_ANSWERING, "Try again"])
            back = sv.LocalServer((sv.HOST, port), data_for=self.fake)       # clark is opened again, on the same port
            threading.Thread(target=back.serve_forever, daemon=True).start()
            self.addCleanup(lambda: (back.shutdown(), back.server_close()))
            self.recovers(cdp, sid)

    def test_a_wrong_token_says_the_page_is_old_and_try_again_reloads_the_page(self):
        with chrome() as cdp:
            with mock.patch.object(sv, "token_ok", return_value=False):
                sid = self.visit(cdp)
                self.shown(cdp, sid, [WENT_WRONG, STALE, "Try again"])
            cdp.js("document.querySelector('.again').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1') && document.querySelector('h1').textContent", sid)
                                 == "Example Programme", WAIT), "Try again reloaded the page with this run's token")

    def test_a_refusal_with_the_servers_old_words_shows_clark_did_not_accept_that_request(self):
        def refuse(handler):
            handler.send(403, {"ok": False, "message": "Not allowed"})
            return False
        with chrome() as cdp:
            with mock.patch.object(sv.Handler, "authorised", refuse):
                sid = self.visit(cdp)
                self.shown(cdp, sid, [WENT_WRONG, NOT_ACCEPTED, "Try again"])
            cdp.js("document.querySelector('.again').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1') && document.querySelector('h1').textContent", sid)
                                 == "Example Programme", WAIT), "Try again reloaded the page")

    def test_a_message_the_page_does_not_know_is_never_shown(self):
        odd = "ValueError: bad JSON in /Users/someone/file.py"
        cases = {500: HIT_PROBLEM, 400: "clark could not read that request. Reload the page.", 403: NOT_ACCEPTED, 409: READ_FAILED}
        for code, wanted in cases.items():
            def route(handler, code=code):
                handler.send(code, {"ok": False, "message": odd})
            with self.subTest(status=code), mock.patch.dict(sv.GET_ROUTES, {"/api/data": route}), chrome() as cdp:
                sid = self.visit(cdp)
                self.shown(cdp, sid, [WENT_WRONG, wanted, "Try again"])
        def missing(handler):
            handler.send(404, {"ok": False, "message": odd})
        with mock.patch.dict(sv.GET_ROUTES, {"/api/data": missing}), chrome() as cdp:
            sid = self.visit(cdp)
            self.shown(cdp, sid, ["That project isn't here", "Check the project's code."])

    def test_the_empty_pages_say_what_is_happening_or_coming(self):
        none = Running(data_for=self.fake, page_html=lambda: page.page_html(tempfile.mkdtemp()), projects=lambda: [])   # #36: no projects yet
        self.addCleanup(none.close)
        with chrome() as cdp:
            sid = navigate(cdp, none.port, "#dashboard")
            self.shown(cdp, sid, ["No project open", "There are no projects yet.",
                                  "To look around with made-up projects, close clark and start it again with python3 -m clark --demo."])
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#report')", sid), WAIT))
            cdp.js("document.querySelector('[data-view=settings]').click()", sid)
            self.shown(cdp, sid, ["Settings", "Settings are not ready yet."])
        self.fake.mode = "wait"
        with chrome() as cdp:
            sid = self.visit(cdp)
            self.shown(cdp, sid, ["Loading", "Opening ABC."])
            self.fake.release.set()

    def test_a_count_and_its_noun_agree_through_one_helper(self):
        """#130 point 7: "1 day", never "1 days"; the helper is workItems.js `plural`, and no source joins a count to a noun by hand."""
        from test_work_items import CHROME, bundled  # noqa: E402
        script = bundled() + ";JSON.stringify([WI.plural(0, 'day'), WI.plural(1, 'day'), WI.plural(2, 'day'), WI.plural(1, 'open action'), WI.plural(3, 'open action'), WI.plural(2, 'entry', 'entries')])"
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            got = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)["result"]["value"]
        self.assertEqual(got, '["0 days","1 day","2 days","1 open action","3 open actions","2 entries"]')
        for name in ("workItems.js", "filters.js", "glanceTiles.js"):
            text = (PAGE_SRC / name).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"\$\{[^}]*\}\s+(days|items|actions|risks|decisions)\b|item\$\{", text), name)

    def test_the_empty_pages_say_why_and_name_one_control(self):
        empty = {"project": {"code": "EMP", "name": "Empty Project"}, "milestones": [], "workstreams": [], "actions": [], "raid": [],
                 "decisions": [], "use_cases": [], "links": [], "labels": {}, "report_sections": []}
        s = Running(data_for=lambda code: empty, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        want = {"#dashboard&p=EMP": "This report has no sections yet. Switch to Edit to add one.",
                "#work&p=EMP": "This project has no work items yet. Use Add item to add the first.",
                "#milestones&p=EMP": "This project has no milestones yet. They appear here once the project record has some."}
        with chrome() as cdp:
            sid = navigate(cdp, s.port, "#dashboard&p=EMP")
            for hash_, words in want.items():
                cdp.js("location.hash = %r" % hash_, sid)
                self.assertTrue(wait(lambda: words in " ".join(lines(cdp, sid)), WAIT), f"{hash_}: {lines(cdp, sid)}")
        self.assertIsNone(NEVER.search(" ".join(want.values())))

    def test_no_text_the_page_shows_names_a_file_path_or_a_file_type(self):
        """#130 point 7: body copy names a folder by its name, never a path (the one command in the no-projects help is typed, not a path)."""
        path = re.compile(r"(?<![\w.])(~/|/Users/|[A-Za-z]:\\|\w+/\w+\.\w+)|\.(html|xlsx|json|db|md)\b")
        for f in [f for f in PAGE_SRC.rglob("*.jsx")]:
            for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                shown = re.findall(r">([^<>{}]{8,})<|\"([A-Z][^\"]{20,})\"", line)
                for a, b in shown:
                    self.assertIsNone(path.search(a or b), f"{f.name}:{n}: {line.strip()}")
        for name in ("publish.py", "to_client.py"):
            text = (Path(page.PAGE).parents[1] / name).read_text(encoding="utf-8")
            self.assertNotIn("The folder {folder} isn't there", text)
            self.assertNotIn("was saved in {folder},", text)

    def test_no_text_in_the_page_source_says_report_editor_or_capital_clark(self):
        files = [f for f in PAGE_SRC.rglob("*") if f.is_file()] + [PAGE_SRC.parent / "shell.css"]
        self.assertTrue(files)
        for f in files:
            text = f.read_text(encoding="utf-8").replace("X-Clark-Token", "")     # the header's name is the server's, not text
            self.assertNotIn("report editor", text.lower(), f.name)
            self.assertNotIn("Clark", text, f.name)
            self.assertIsNone(re.search(r"\bJSON\b(?!\.)", re.sub(r"//.*", "", text)) if f.suffix == ".jsx" else None, f.name)


if __name__ == "__main__":
    unittest.main()
