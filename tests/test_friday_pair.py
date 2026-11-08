"""#576 (from #570): the Report bar's Friday rule (ReportBar.jsx isFriday and notFriday) and the server's (changes.py, the
week_ending check) must not drift apart. For every day over a run that holds a year end and a leap day, the page and the server
agree on whether the day is a Friday, and, when it is not, on the Friday they offer.

Run: python3 dev/run_tests.py test_friday_pair
Quick tier: no browser. The two lines are cut out of ReportBar.jsx itself and run in node beside the page's own weekEndOf and
shownDay (bundled by the pinned esbuild); the tests skip when node is not on the machine. client_filters.week_end (the Sunday
of the client filters) is a separate question for the owner (#576); it is not part of this pair.
"""
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)
from clark import changes  # noqa: E402

PAGE = SRC / "clark" / "page" / "src"
BAR = (PAGE / "edit" / "ReportBar.jsx").read_text(encoding="utf-8")
ENTRY = 'export { weekEndOf } from "./logic/board.js";\nexport { shownDay } from "./logic/week.js";\n'


def the_page_says(days):
    """{day: [isFriday, notFriday words]} as ReportBar.jsx's own two lines give them."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    lines = [re.search(r"^export (const %s = .*;)\s*(?://.*)?$" % name, BAR, re.M) for name in ("isFriday", "notFriday")]
    assert all(lines), "ReportBar.jsx no longer has its isFriday and notFriday lines in this shape"
    with tempfile.TemporaryDirectory() as tmp:
        entry = Path(tmp) / "entry.js"
        entry.write_text(ENTRY.replace('"./logic', '"%s' % (PAGE / "logic")), encoding="utf-8")
        out = Path(tmp) / "w.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=W", str(entry), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconst { weekEndOf, shownDay } = W;\n" + "\n".join(m.group(1) for m in lines)
                          + ";\nconsole.log(JSON.stringify(%s.map((d) => [d, isFriday(d), notFriday(d)])));" % json.dumps(days), encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return {d: [f, words] for d, f, words in json.loads(got.stdout)}


def the_server_says(day):
    """None when the server accepts `day` as a week ending, else the words it refuses with."""
    try:
        changes._checked_project_changes({"week_ending": day})
    except changes.Refused as e:
        return str(e)
    return None


class FridayPair(unittest.TestCase):
    DAYS = [(date(2023, 12, 20) + timedelta(days=n)).isoformat() for n in range(21)] + \
           [(date(2024, 2, 22) + timedelta(days=n)).isoformat() for n in range(14)] + \
           [(date(2026, 12, 25) + timedelta(days=n)).isoformat() for n in range(14)]

    def test_the_page_and_the_server_agree_on_every_day(self):
        page = the_page_says(self.DAYS)
        fridays = 0
        for day in self.DAYS:
            with self.subTest(day=day):
                server = the_server_says(day)
                self.assertEqual(page[day][0], server is None, "the page and the server disagree on whether this is a Friday")
                if server is None:
                    fridays += 1
                else:
                    self.assertEqual(page[day][1], server, "the page offers the Friday the server names")
        self.assertEqual(fridays, 7, "the run holds seven Fridays: the check looked at both answers")
        self.assertEqual(sum(1 for d in self.DAYS if "2024-02-29" == d), 1, "and the leap day")


if __name__ == "__main__":
    unittest.main()
