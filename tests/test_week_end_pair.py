"""#576 The week end: the page's report bar and the server say the same thing, and the Sunday week end stays Sunday.

Run: python3 dev/run_tests.py test_week_end_pair
Two week ends exist on purpose. The Week ending of the report is a Friday (#570): the page's ReportBar.jsx (isFriday, notFriday) and
the server's changes.py (the refusal NOT_FRIDAY) must agree on which days are Fridays and on which Friday is named instead.
The client report's "this week" / "next week" bucket (client_filters.week_end) ends on a Sunday and stays so (head ruling on #576:
no change of behaviour). This file reads the real ReportBar.jsx (bundled the way the page is, run by Node, no browser) and the real
server code over 400 consecutive days (a leap day and two year ends among them), so a change on either side that the other does
not follow fails here. Node is needed (CI has it); without it on a computer the test is skipped.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from _paths import SRC
import build_page  # noqa: E402  (dev/tools)
import esbuild  # noqa: E402  (dev/tools)
from clark import changes, client_filters

REPORT_BAR = SRC / "clark" / "page" / "src" / "edit" / "ReportBar.jsx"
DAYS = [(date(2027, 12, 20) + timedelta(days=i)).isoformat() for i in range(400)]      # 2027-12-20 to 2029-01-23: 2028-02-29 and two year ends


def page_answers(days):
    """{day: [isFriday, notFriday]} from the real ReportBar.jsx, run by Node."""
    if shutil.which("node") is None and not os.environ.get("CI"):
        raise unittest.SkipTest("node is not installed on this computer (CI has it)")
    with tempfile.TemporaryDirectory() as tmp:
        entry, out = Path(tmp) / "entry.js", Path(tmp) / "bar.js"
        entry.write_text(f'import {{ isFriday, notFriday }} from {json.dumps(str(REPORT_BAR))};\n'
                         f'const days = {json.dumps(days)};\n'
                         'console.log(JSON.stringify(Object.fromEntries(days.map((d) => [d, [isFriday(d), notFriday(d)]]))));\n', encoding="utf-8")
        done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--tsconfig-raw={}", *build_page.preact_flags(held=False), str(entry), f"--outfile={out}"],
                           cwd=SRC, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        # the bar's stores listen to the window when loaded; Node has none, so the bundle starts after a stand-in
        out.write_text("globalThis.addEventListener = () => {};\n" + out.read_text(encoding="utf-8"), encoding="utf-8")
        ran = subprocess.run(["node", str(out)], capture_output=True, text=True)
        assert ran.returncode == 0, ran.stderr
        return json.loads(ran.stdout)


def server_answer(day):
    """None when the server takes the day as a week ending, else the words of its refusal."""
    try:
        changes._checked_project_changes({"week_ending": day})
    except changes.Refused as refused:
        return refused.message
    return None


class Pair(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = page_answers(DAYS)

    def test_the_page_and_the_server_agree_on_every_day_which_are_fridays(self):
        for day in DAYS:
            with self.subTest(day=day):
                self.assertEqual(self.page[day][0], server_answer(day) is None)
                self.assertEqual(self.page[day][0], date.fromisoformat(day).weekday() == 4)

    def test_both_name_the_same_friday_in_the_same_words(self):
        for day in DAYS:
            if self.page[day][0]:
                continue
            with self.subTest(day=day):
                self.assertEqual(self.page[day][1], server_answer(day))

    def test_the_friday_named_is_the_one_on_or_after_the_day(self):
        for day in DAYS:
            if self.page[day][0]:
                continue
            d = date.fromisoformat(day)
            friday = d + timedelta(days=(4 - d.weekday()) % 7)
            with self.subTest(day=day):
                self.assertEqual(server_answer(day), changes.NOT_FRIDAY.format(friday=friday.strftime("%d-%m-%Y")))

    def test_there_are_fridays_and_other_days_in_the_range(self):
        self.assertEqual(sum(v[0] for v in self.page.values()), len([d for d in DAYS if date.fromisoformat(d).weekday() == 4]))
        self.assertGreater(sum(v[0] for v in self.page.values()), 50)


class Sunday(unittest.TestCase):
    def test_the_client_bucket_week_end_stays_the_sunday_on_or_after_the_day(self):
        for day in DAYS:
            d = date.fromisoformat(day)
            sunday = (d + timedelta(days=(6 - d.weekday()) % 7)).isoformat()
            with self.subTest(day=day):
                self.assertEqual(client_filters.week_end(day), sunday)
                self.assertEqual(client_filters.week_end(day, 1), (date.fromisoformat(sunday) + timedelta(days=7)).isoformat())
                self.assertEqual(date.fromisoformat(client_filters.week_end(day)).weekday(), 6)

    def test_on_a_working_day_the_sunday_is_two_days_after_the_friday_the_report_bar_names(self):
        for day in DAYS:
            d = date.fromisoformat(day)
            if d.weekday() > 4:
                continue
            friday = d + timedelta(days=4 - d.weekday())
            with self.subTest(day=day):
                self.assertEqual(client_filters.week_end(day), (friday + timedelta(days=2)).isoformat())


if __name__ == "__main__":
    unittest.main()
