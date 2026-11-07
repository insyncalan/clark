"""Shared helpers for the #944 T2 brand tests: temp library roots, zips on disk, byte snapshots of a folder.

The contract these tests pin for src/clark/brands.py (see the T2 test list):
  brands.review(path, root) -> dict; brands.install(review_id, root, data); brands.remove(brand_id, root, data);
  brands.undo(root, data); brands.installed(root); brands.folder(root, brand_id); brands.recover(root);
  brands.in_use(brand_id) (a context manager a publish or export holds); brands.GENERIC; brands.DENY_WORDS;
  brands.clock (a function returning seconds, patched by tests); brands.after_write (a hook called with the staged folder
  after the files are written and before they are checked again); brands.BrandError with .key, .message, .detail.
`root` holds system/branding/; `data` is the data folder (brand-backups/ goes in it).
"""
import os
import tempfile
from pathlib import Path

import _brand_zips as bz

HIDDEN_NEW = ".clark-brand-new-"
HIDDEN_OLD = ".clark-brand-old-"


def snapshot(folder):
    """{relative path: bytes (or None for a folder)} of everything under folder, links not followed."""
    out = {}
    folder = Path(folder)
    if not folder.exists():
        return out
    for dirpath, dirs, files in os.walk(folder):
        for n in dirs:
            out[str((Path(dirpath) / n).relative_to(folder))] = None
        for n in files:
            p = Path(dirpath) / n
            out[str(p.relative_to(folder))] = None if p.is_symlink() else p.read_bytes()
    return out


def make_dirs(case):
    """(root, data, scratch) temp folders, removed after the test; root/system/branding exists."""
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    base = Path(tmp.name)
    root, data, scratch = base / "app", base / "data", base / "downloads"
    (root / "system" / "branding").mkdir(parents=True)
    data.mkdir()
    scratch.mkdir()
    return root, data, scratch


def write_zip(scratch, data, brand_id=bz.BRAND_ID, version="1.0.0", name=None):
    path = Path(scratch) / (name or bz.zip_name(brand_id, version))
    path.write_bytes(data)
    return path


def branding(root):
    return Path(root) / "system" / "branding"
