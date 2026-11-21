"""Row 1046 (v1.2), piece 1: the bell's notices, the logic (src/clark/page/src/logic/notices.js) with nothing drawn yet.

Run: python3 dev/run_tests.py test_notices_logic
The repo has no Node, so the logic runs inside headless Chrome (the harness test_safety_logic.py uses). Chrome is required; no
width matters, the page draws nothing. Fixture data is made up.
"""
import contextlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "notices_demo.jsx"


_PAGE = {}


def test_page_html():
    if "html" not in _PAGE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        css = (build_page.TOKENS.read_text(encoding="utf-8") + (build_page.PAGE / "shell.css").read_text(encoding="utf-8"))
        css = css.replace("</style", "<\\/style")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8">'
                         f'<meta name="viewport" content="width=device-width, initial-scale=1"><title>t</title>'
                         f'<style>\n{css}</style></head>\n<body><div id="root"></div>\n'
                         f'<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


class InBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=test_page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.load()

    def load(self, width=1400, height=900, theme="light"):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.logic)", self.sid)), "the test bundle ran")
        self.js(f"document.documentElement.dataset.theme = {lit(theme)}")

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def val(self, expr):
        got = self.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()")
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)


def n(id, date="2030-10-10", **kw):
    return {"id": id, "title": "Title " + id, "body": "One sentence.", "date": date, **kw}


class Logic(InBrowser):
    def shown(self, notices, today="2030-10-12", installed=None):
        return self.val(f"T.logic.visible({lit(notices)}, {{today: {lit(today)}, installed: {lit(installed)}}})")

    def ids(self, notices, **kw):
        return [x["id"] for x in self.shown(notices, **kw)]

    def test_badge_is_empty_at_zero_the_number_to_nine_then_nine_plus(self):
        got = {c: self.val(f"T.logic.badgeText({c})") for c in (0, 1, 9, 10, 250)}
        self.assertEqual(got, {0: "", 1: "1", 9: "9", 10: "9+", 250: "9+"})

    def test_the_bell_name_has_the_true_count_and_the_bell_shows_only_with_something_unread(self):
        self.assertEqual(self.val("T.logic.bellName(14)"), "Notifications, 14 unread")
        self.assertEqual([self.val(f"T.logic.bellShown({c})") for c in (0, 1)], [False, True])

    def test_one_notice_per_id_the_newest_date_wins(self):
        got = self.shown([n("a", "2030-10-01", title="old"), n("a", "2030-10-05", title="new"), n("a", "2030-10-02", title="mid")])
        self.assertEqual([(x["id"], x["title"]) for x in got], [("a", "new")])

    def test_equal_dates_the_later_one_in_the_list_wins(self):
        got = self.shown([n("a", "2030-10-05", title="first"), n("a", "2030-10-05", title="second")])
        self.assertEqual([(x["id"], x["title"]) for x in got], [("a", "second")])

    def test_newest_first_then_by_id(self):
        self.assertEqual(self.ids([n("b", "2030-10-05"), n("c", "2030-10-09"), n("a", "2030-10-05")]), ["c", "a", "b"])

    def test_expired_goes_but_the_last_day_stays(self):
        self.assertEqual(self.ids([n("x", expires="2030-10-11"), n("y", expires="2030-10-12"), n("z")]), ["y", "z"])

    def test_ninety_days_stay_and_ninety_one_go(self):
        self.assertEqual(self.ids([n("in", "2030-07-14"), n("out", "2030-07-13")], today="2030-10-12"), ["in"])

    def test_at_most_thirty_kept_the_newest(self):
        many = [n(f"n{i:02d}", f"2030-09-{(i % 28) + 1:02d}") for i in range(40)]
        got = self.shown(many)
        self.assertEqual(len(got), 30)
        self.assertTrue(all(got[i]["date"] >= got[i + 1]["date"] for i in range(29)))

    def test_a_version_test_shows_the_notice_only_while_the_installed_version_is_below(self):
        test = {"installedBelow": "1.0.7"}
        for installed, want in (("1.0.6", ["v"]), ("1.0.7", []), ("1.0.10", []), ("0.9.9", ["v"]), (None, ["v"]), ("rubbish", ["v"])):
            self.assertEqual(self.ids([n("v", test=test)], installed=installed), want, installed)

    def test_versions_compare_as_numbers_not_text(self):
        self.assertEqual([self.val(f"T.logic.compareVersions({lit(a)}, {lit(b)})") for a, b in (("1.0.10", "1.0.7"), ("1.0", "1.0.0"), ("1.0.7", "1.1"))], [1, 0, -1])
        self.assertIsNone(self.val("T.logic.compareVersions('x', '1.0')"))      # NaN comes back from JSON as null

    def test_a_notice_without_an_id_title_or_real_date_is_dropped(self):
        bad = [{"title": "t", "date": "2030-10-10"}, {"id": "a", "date": "2030-10-10"}, n("b", "2030-02-30"), n("c", "10-10-2030"), "text", None, 7]
        self.assertEqual(self.ids(bad + [n("ok")]), ["ok"])

    def test_text_is_plain_cut_and_never_html(self):
        got = self.shown([n("a", title="<b>Hi</b>\n there", body="x" * 500)])[0]
        self.assertEqual(got["title"], "<b>Hi</b> there")      # kept as text: the page draws text, never markup
        self.assertEqual(len(got["body"]), 240)

    def test_an_action_is_two_words_or_fewer_and_names_a_place_inside_clark(self):
        def action(label, to):
            return self.shown([n("a", action={"label": label, "to": to})])[0].get("action")
        self.assertEqual(action("Open Settings", "/settings"), {"label": "Open Settings", "to": "/settings"})
        for to in ("https://example.com/", "//example.com/", "javascript:alert(1)", "settings", "/a/../b", "mailto:a@b.c", ""):
            self.assertIsNone(action("Open", to), to)
        self.assertEqual(action("Open the settings", "/settings"), None)      # three words
        self.assertIsNone(action("Open the settings page", "/settings"))
        self.assertIsNone(action("", "/settings"))

    def test_an_unknown_severity_is_info_and_each_has_its_word(self):
        self.assertEqual([x["severity"] for x in self.shown([n("a", severity="loud"), n("b", severity="critical")])], ["info", "critical"])
        self.assertEqual(self.val("T.logic.LABELS"), {"info": "Info", "warning": "Warning", "critical": "Critical"})

    def test_unread_marking_and_pruning(self):
        shown = self.shown([n("a"), n("b"), n("c")])
        self.assertEqual(self.val(f"T.logic.unreadIds({lit(shown)}, ['b'])"), ["a", "c"])
        self.assertEqual(self.val("T.logic.markRead(['a'], 'b')"), ["a", "b"])
        self.assertEqual(self.val("T.logic.markRead(['a'], 'a')"), ["a"])
        self.assertEqual(self.val(f"T.logic.markAllRead(['a'], {lit(shown)})"), ["a", "b", "c"])
        self.assertEqual(self.val("T.logic.unreadIds([], null)"), [])
        self.assertEqual(self.val("T.logic.pruneRead(['a', 'gone'], ['a', 'b'])"), ["a"])

    def test_arrivals_the_first_look_announces_nothing(self):
        shown = self.shown([n("a"), n("b")])
        self.assertEqual(self.val(f"T.logic.arrivals(null, {lit(shown)})"), [])
        self.assertEqual(self.val(f"T.logic.arrivals(['a'], {lit(shown)})"), ["b"])

    def test_the_words_are_the_ones_listed_for_the_ruling(self):
        self.assertEqual(self.val("T.logic.WORDS"), {"caughtUp": "You are all caught up", "markRead": "Mark as read", "markAll": "Mark all as read", "close": "Close"})
