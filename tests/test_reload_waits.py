"""#419: a test that reloads the page waits for the NEW page (tests/_new_page.py), never reads straight after.

`location.reload()` and Chrome's Page.reload return while the old document is still up, so a read made straight afterwards can see the
old page, and Chrome answers a call made in that gap with 'Inspected target navigated or closed' (seen on the hosted macOS runner).
Every line in tests/*.py that reloads must have, within a few lines of it, the marker set on the old page (`__old_document`) and the
shared wait (`until_new_page`). A test that reloads without them fails here, and the message lists it.
"""
import re
import unittest

from _paths import TESTS

RELOAD = re.compile(r"""location\.reload\(\)|["']Page\.reload["']""")
BEFORE, AFTER = 3, 4
SKIP = {"_new_page.py", "test_reload_waits.py"}        # these only talk about reloading


def offenders(name, text):
    """The 'file:line' of each reload in `text` that has no marker and no shared wait close to it."""
    lines = text.splitlines()
    found = []
    for i, line in enumerate(lines):
        if not RELOAD.search(line) or line.lstrip().startswith("#"):
            continue
        near = "\n".join(lines[max(0, i - BEFORE):i + AFTER + 1])
        if "__old_document" not in near or "until_new_page" not in near:
            found.append(f"{name}:{i + 1}")
    return found


class ReloadWaits(unittest.TestCase):
    def test_every_reload_in_the_tests_waits_for_the_new_page(self):
        bad = []
        for path in sorted(TESTS.glob("*.py")):
            if path.name not in SKIP:
                bad += offenders(path.name, path.read_text(encoding="utf-8"))
        self.assertEqual(bad, [], "these reload without the marker and until_new_page (tests/_new_page.py): " + ", ".join(bad))

    def test_the_check_catches_a_bare_reload_and_passes_a_waited_one(self):
        bare = 'p.js("location.reload()")\np.until("!!document.querySelector(\'#x\')", "again")\n'
        self.assertEqual(offenders("t.py", bare), ["t.py:1"])
        self.assertEqual(offenders("t.py", 'cdp.call("Page.reload", {}, sid)\nx = 1\n'), ["t.py:1"])
        waited = ('p.js("window.__old_document = true")\np.js("location.reload()")\n'
                  'p.until_new_page("window.__old_document === undefined && !!document.querySelector(\'#x\')", "again")\n')
        self.assertEqual(offenders("t.py", waited), [])
        self.assertEqual(offenders("t.py", "# location.reload() is described here\n"), [])


if __name__ == "__main__":
    unittest.main()
