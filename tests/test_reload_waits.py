"""#419: a test that reloads the page waits for the NEW page before it reads (no Chrome; quick tier).

`location.reload()` and `Page.reload` return while the old page is still up, so a test that reloads and then waits for something the
old page already shows reads the page that is about to go away (the flake PR 208 / #283 removed from five tests). The wait is
`_new_page.py` (`reload_to_new_page`, `reload_to_new_page_cdp`). This file scans every file in tests/ for a reload that is not made
through it and fails on any that is not in ACCEPTED below, with the one-line reason it waits another way. It reads the sources
only: it starts no browser.
"""
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

# What counts as a reload in a test's code: Chrome's own, or the page's.
RELOAD = re.compile(r"""["']Page\.reload["']|\blocation\.reload\(""")

# The files that are not scanned: the helper that makes the reload, and this file (its samples hold the words).
SKIP = {"_new_page.py", Path(__file__).name}

# A reload made some other way is accepted only if it is listed here: (file, text of the line, why it still waits for the new page).
# Each one must set a token on the old window (`window.__...`) on its own line or within the two lines above it.
ACCEPTED = (
    ("test_palette.py", 'p.js("location.reload()")', "sets window.__old_document, then until_new_page waits for it to go"),
    ("test_section_style_cards.py", "window.__before = 1; location.reload()", "settled() waits for window.__before to go"),
    ("test_about_you.py", "window.__before_reload = true; location.reload()", "the next wait needs window.__before_reload to be gone"),
    ("test_ask_settings.py", "window.__beforeReload = true; localStorage.clear(); location.reload()",
     "the next wait needs window.__beforeReload to be gone"),
    ("test_undo_key.py", 'cdp.call("Page.reload", {}, sid)', "sets window.__before_reload, then waits for it to be gone"),
)
TOKEN = re.compile(r"window\.__\w+")


def unwaited(lines, accepted=()):
    """The (line number, text) of every reload in `lines` that is not on an `accepted` line. `accepted` is a list of line texts.
    A comment line is not a reload. A line that is accepted must have a token set on the old window on it or just above."""
    found = []
    for n, line in enumerate(lines):
        text = line.strip()
        if text.startswith("#") or not RELOAD.search(line):
            continue
        near = " ".join(lines[max(0, n - 2):n + 1])
        if any(a in line for a in accepted) and TOKEN.search(near):
            continue
        found.append((n + 1, text))
    return found


def scan(folder=HERE, accepted=ACCEPTED):
    """Every unwaited reload in the folder's .py files, as 'file:line: text'; and every accepted entry that no longer matches."""
    problems, used = [], set()
    for path in sorted(folder.glob("*.py")):
        if path.name in SKIP:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        mine = [(i, a) for i, (f, a, _) in enumerate(accepted) if f == path.name]
        for n, text in unwaited(lines, [a for _, a in mine]):
            problems.append(f"{path.name}:{n}: {text}")
        for i, a in mine:
            if any(a in line and RELOAD.search(line) for line in lines):
                used.add(i)
    for i, (f, a, _) in enumerate(accepted):
        if i not in used:
            problems.append(f"{f}: accepted entry matches no reload any more: {a}")
    return problems


class ReloadWaits(unittest.TestCase):
    def test_every_reload_in_tests_waits_for_the_new_page(self):
        problems = scan()
        self.assertEqual(problems, [], "reload through _new_page.reload_to_new_page (or _cdp), or list the site in ACCEPTED with its reason:\n"
                         + "\n".join(problems))

    def test_every_accepted_site_has_a_reason(self):
        for f, a, why in ACCEPTED:
            with self.subTest(file=f):
                self.assertTrue((HERE / f).is_file(), f)
                self.assertTrue(a.strip() and why.strip(), "a line and a reason")


class ScanCanFail(unittest.TestCase):
    """The scan is only worth having if it can fail: these samples are what it must and must not flag."""

    def test_a_bare_chrome_reload_is_flagged(self):
        got = unwaited(['    cdp.call("Page.reload", {}, sid)', '    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector(\'#peek\')", sid)))'])
        self.assertEqual(got, [(1, 'cdp.call("Page.reload", {}, sid)')])

    def test_a_bare_page_reload_is_flagged(self):
        self.assertEqual(len(unwaited(['p.js("location.reload()")', 'p.until("!!document.querySelector(\'#list\')", "again")'])), 1)

    def test_a_reload_that_sets_a_token_and_is_listed_passes(self):
        lines = ['p.js("window.__old_document = true")', 'p.js("location.reload()")']
        self.assertEqual(unwaited(lines, ['p.js("location.reload()")']), [])

    def test_a_listed_reload_with_no_token_is_still_flagged(self):
        self.assertEqual(len(unwaited(['p.js("location.reload()")'], ['p.js("location.reload()")'])), 1)

    def test_a_reload_that_is_not_listed_is_flagged_even_with_a_token(self):
        self.assertEqual(len(unwaited(['p.js("window.__x = 1")', 'p.js("location.reload()")'], [])), 1)

    def test_the_helper_call_and_a_comment_are_not_reloads(self):
        self.assertEqual(unwaited(["reload_to_new_page_cdp(cdp, sid)", "reload_to_new_page(p.js)", "# a Page.reload here is a comment: 'Page.reload'"]), [])

    def test_a_stale_accepted_entry_is_reported(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "test_x.py").write_text("x = 1\n", encoding="utf-8")
            self.assertEqual(len(scan(Path(d), (("test_x.py", 'p.js("location.reload()")', "why"),))), 1)

    def test_a_bare_reload_in_a_file_is_found_by_scan(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "test_x.py").write_text('cdp.call("Page.reload", {}, sid)\n', encoding="utf-8")
            self.assertEqual(scan(Path(d), ()), ['test_x.py:1: cdp.call("Page.reload", {}, sid)'])


if __name__ == "__main__":
    unittest.main()
