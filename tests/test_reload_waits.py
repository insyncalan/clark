"""#419: a test that reloads the page by script waits for the NEW page before it reads, with the helper #283 added.

Chrome answers a call made while the page is navigating with 'Inspected target navigated or closed', and location.reload() returns
while the old page is still up. So every `location.reload()` in a browser test must be followed, within a few lines, by
until_new_page (or settled), which waits that gap out."""

import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
WAITS = ("until_new_page", "settled(")
LOOK_AHEAD = 4


def reloads_without_wait(lines):
    return [n + 1 for n, line in enumerate(lines)
            if "location.reload()" in line and not line.lstrip().startswith(("#", '"'))
            and not any(w in "\n".join(lines[n:n + 1 + LOOK_AHEAD]) for w in WAITS)]


class ReloadWaits(unittest.TestCase):
    def test_every_script_reload_in_a_test_is_followed_by_the_new_page_wait(self):
        bad = []
        for path in sorted(HERE.glob("test_*.py")):
            if path.name == Path(__file__).name:
                continue
            bad += [f"{path.name}:{n}" for n in reloads_without_wait(path.read_text().splitlines())]
        self.assertEqual(bad, [], "these reload by script and read without waiting for the new page")

    def test_the_check_sees_a_reload_with_no_wait(self):
        self.assertEqual(reloads_without_wait(['p.js("location.reload()")', 'p.until("x", "y")']), [1])
        self.assertEqual(reloads_without_wait(['p.js("location.reload()")', 'p.until_new_page("x", "y")']), [])


if __name__ == "__main__":
    unittest.main()
