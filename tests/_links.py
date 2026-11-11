"""Shared by the tests that make symbolic links: skip them where the system does not allow one."""
import shutil
import tempfile
import unittest
from pathlib import Path


def needs_links(test):
    """Symbolic links need rights on Windows that a plain run may not have; the test is skipped there when one cannot be made."""
    d = Path(tempfile.mkdtemp())
    try:
        (d / "l").symlink_to(d, target_is_directory=True)
    except (OSError, NotImplementedError):
        return unittest.skip("this system does not allow symbolic links here")(test)
    finally:
        shutil.rmtree(d, True)
    return test
