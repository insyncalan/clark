"""Repo paths for tests. Import these rather than working paths out in each test.

Importing this module also puts src/, dev/tools/ and vendor/ on sys.path (as dev/run_tests.py does), so a test that
imports it first also runs under plain `python3 -m unittest discover -s tests`.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
VENDOR = ROOT / "vendor"
TESTS = ROOT / "tests"
TOOLS = ROOT / "dev" / "tools"

for _folder in (VENDOR, TOOLS, SRC):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))


def _build_pages():
    """The generated pages (#495, #563) are not committed: build them once, here, so a test run alone on a fresh checkout finds
    page.html and page-view.html. Every test imports this module first. The build is stamped and locked (page.ensure_built), so
    this costs one hash when the pages are current. A failure is printed, and the test that needs a page then fails on its own."""
    try:
        from clark import page
        page.ensure_built()
    except Exception as exc:        # noqa: BLE001  (a PageError, or no bundler offline)
        print("tests/_paths.py: the pages were not built: %s" % exc, file=sys.stderr)


_build_pages()


def _block_the_network():
    """No test reaches the real network by default (Row 1327): the updater's default opener (clark.release_fetch.default_opener) is
    swapped for one that fails the way an offline computer does, and counts the call in `calls`. A test that wants a lookup gives
    the Updater its own release_opener. Production keeps release_fetch.real_opener."""
    try:
        import urllib.error
        from clark import release_fetch
    except ImportError:
        return

    def no_network(request, timeout):
        no_network.calls.append(getattr(request, "full_url", str(request)))
        raise urllib.error.URLError("no network in tests")
    no_network.calls = []
    release_fetch.default_opener = no_network


_block_the_network()
