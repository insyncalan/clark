#!/usr/bin/env python3
"""Make a brand zip for clark's Settings: python3 tools/make_brand_zip.py <brand folder> <output folder>

The brand folder holds clark-brand.json ({"id", "name", "version"}), tokens.css and the pictures under assets/. The zip is
named clark-brand-<id>-<version>.zip, holds one top folder <id>/, a manifest that lists every file with its size, sha256 and
mode, and is the same bytes every time. The same checks run as when clark reviews the zip, with the same sentences.
"""
import hashlib
import io
import json
import os
import stat
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from clark import brands                                    # noqa: E402

DATE = (1980, 1, 1, 0, 0, 0)


def _info(name):
    info = zipfile.ZipInfo(name, DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    return info


def _read(folder):
    """({rel: bytes}, manifest dict) of a brand folder. A link, a name clark doesn't use, or a file over the cap is refused."""
    files, stack = {}, [""]
    while stack:
        rel = stack.pop()
        here = folder / rel if rel else folder
        for name in sorted(os.listdir(here)):
            sub = (rel + "/" + name) if rel else name
            mode = os.lstat(here / name).st_mode
            if stat.S_ISLNK(mode):
                raise brands.BrandError("link", sub)
            if stat.S_ISDIR(mode):
                stack.append(sub)
            elif not stat.S_ISREG(mode):
                raise brands.BrandError("file_name", sub)
            elif os.lstat(here / name).st_size > brands.MEMBER_CAP:
                raise brands.BrandError("too_big", sub)
            else:
                files[sub] = (here / name).read_bytes()
    raw = files.pop(brands.MANIFEST, None)
    doc = brands._parse_manifest(raw) if raw is not None else None
    if doc is None:
        raise brands.BrandError("manifest", "clark-brand.json is missing or not an object")
    return files, doc


def make(folder):
    """The zip, as bytes, for the brand folder; raises brands.BrandError."""
    files, doc = _read(Path(folder))
    brand_id = doc.get("id")
    brands.check_id(brand_id)
    doc = dict(doc, files=[{"path": rel, "size": len(body), "sha256": hashlib.sha256(body).hexdigest(), "mode": "0644"}
                           for rel, body in sorted(files.items())])
    brands._check_manifest(doc)
    brands.check_content(doc["name"], files)
    manifest = json.dumps({k: doc[k] for k in ("id", "name", "version", "files")}, sort_keys=True, indent=2).encode() + b"\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compresslevel=9) as z:
        z.writestr(_info("%s/%s" % (brand_id, brands.MANIFEST)), manifest)
        for rel, body in sorted(files.items()):
            z.writestr(_info("%s/%s" % (brand_id, rel)), body)
    return buf.getvalue()


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    try:
        data = make(argv[0])
        doc = json.loads((Path(argv[0]) / brands.MANIFEST).read_text(encoding="utf-8"))
        out = Path(argv[1]) / ("clark-brand-%s-%s.zip" % (doc["id"], doc["version"]))
        out.write_bytes(data)
    except brands.BrandError as e:
        print(e.message)
        return 1
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
