"""Tech debt #307: "I sent it" shows the server's own refusal, however long its plain sentence is (up to the page's cap).

Run: python3 dev/run_tests.py test_email_sent_refusal
sendEmailSent (page/src/api.js) is bundled with the pinned esbuild and run in node with a stand-in fetch; no browser. Every refusal of
the route now ends "Nothing was saved." and so grows: a refusal over 240 characters used to fall back to the generic line. Part 2
keeps every sentence the route can give under the page's cap, so the generic line is never what a real refusal turns into.
"""
import ast
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts src/ and dev/tools/ on the path)

import build_page  # noqa: E402
import esbuild  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"


def sentence(n):
    """One plain refusal of exactly n characters, ending as the route's do."""
    tail = " Nothing was saved."
    return ("The date on this computer is a long way from today. " * 120)[: n - len(tail)] + tail


class Shown(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("node"):
            raise unittest.SkipTest("no node")
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark-sent-"))
        out = cls.tmp / "api.mjs"
        done = esbuild.run(["--bundle", "--format=esm", "--platform=node", "--tsconfig-raw={}", *build_page.preact_flags(), "api.js",
                            f"--outfile={out}"], cwd=build_page.SRC, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        cls.bundle = out

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def ask(self, status, body):
        """What sendEmailSent answers when the server answers `status` with `body` (a JSON value, or a string sent as it is)."""
        code = ('globalThis.addEventListener = () => {}; globalThis.location = { hash: "", search: "", pathname: "/" };'
                f'globalThis.document = {{ getElementById: () => ({{ textContent: "{{\\"token\\":\\"t\\"}}" }}) }};'
                f'globalThis.fetch = async () => ({{ ok: {json.dumps(status < 400)}, status: {status}, json: async () => ({json.dumps(body)}) }});'
                f'const {{ sendEmailSent }} = await import({json.dumps(self.bundle.as_uri())});'
                'console.log(JSON.stringify(await sendEmailSent("ABC", { ids: ["ABC-A-001"], mode: "chase", date: "2026-11-02" })));')
        done = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_a_refusal_over_240_characters_is_shown_as_the_server_said_it(self):
        for n in (241, 300, 420):
            said = sentence(n)
            self.assertEqual(len(said), n)
            for status in (400, 404, 409):
                self.assertEqual(self.ask(status, {"ok": False, "message": said}), {"ok": False, "message": said}, f"{n} characters, {status}")

    def test_a_short_refusal_is_still_shown_as_it_is(self):
        said = "Tick at least one item before you press I sent it."
        self.assertEqual(self.ask(400, {"ok": False, "message": said}), {"ok": False, "message": said})

    def test_text_that_is_not_a_plain_sentence_gets_the_generic_words(self):
        generic = self.ask(400, {"ok": False})["message"]
        self.assertTrue(generic.strip())
        for body in ({"ok": False, "message": sentence(5000)}, {"ok": False, "message": "Two\nlines. Nothing was saved."},
                     {"ok": False, "message": "   "}, {"ok": False, "message": 7}, None):
            self.assertEqual(self.ask(400, body), {"ok": False, "message": generic}, str(body)[:40])

    def test_the_words_of_a_failure_that_is_not_a_refusal_are_never_shown(self):
        said = sentence(300)
        for status in (403, 500, 503):
            got = self.ask(status, {"ok": False, "message": said})
            self.assertFalse(got["ok"])
            self.assertNotEqual(got["message"], said, status)


class RouteStaysUnderTheCap(unittest.TestCase):
    def cap(self):
        m = re.search(r"const SENT_REFUSAL_MAX = (\d+);", (SRC / "api.js").read_text(encoding="utf-8"))
        self.assertTrue(m, "api.js names the cap as SENT_REFUSAL_MAX")
        return int(m.group(1))

    def test_every_sentence_the_sent_route_can_refuse_with_fits_the_page_cap(self):
        cap, found = self.cap(), []
        store = ast.parse((ROOT / "src" / "clark" / "store.py").read_text(encoding="utf-8"))
        feed = ast.parse((ROOT / "src" / "clark" / "draft_email_feed.py").read_text(encoding="utf-8"))
        fn = next(n for n in ast.walk(store) if isinstance(n, ast.FunctionDef) and n.name == "log_email_sent")
        for node in ast.walk(fn):
            if isinstance(node, ast.Raise) and isinstance(node.exc, ast.Call) and getattr(node.exc.func, "id", "") == "Invalid" and node.exc.args:
                arg = node.exc.args[0]
                if isinstance(arg, ast.Constant):
                    found.append(arg.value)
                elif isinstance(arg, ast.JoinedStr):                      # an f-string: its fixed parts plus up to 3 digits for a number
                    found.append("".join(p.value if isinstance(p, ast.Constant) else "999" for p in arg.values))
        for node in feed.body:                                            # BAD_SENT, BUSY_SENT, and the shared refusals the seam uses
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
                if node.targets[0].id in ("BAD_SENT", "BUSY_SENT", "BAD_CODE", "BAD_PICK", "BAD_DATE"):
                    found.append(node.value.value)
        self.assertGreaterEqual(len(found), 10, "the scan found the route's refusals")
        for said in found:
            self.assertLessEqual(len(said), cap, said)


if __name__ == "__main__":
    unittest.main()
