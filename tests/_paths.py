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
