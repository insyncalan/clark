"""In-memory brand zips for the #944 tests: one valid brand and a set of hostile variants. Standard library only.

A brand zip has ONE top folder <id>/ holding clark-brand.json (id, name, version, files with path, size, sha256 and mode),
tokens.css (only :root custom properties) and pictures under assets/. A member name that starts with '!' is written raw (no
top folder), so a hostile path can be built. Every builder returns the zip as bytes. The bytes are deterministic: fixed dates, members in
sorted order (except where a hostile variant needs a particular order), fixed compression.

Sizes that would be large (a member over 5 MB, a zip over 16 MB) are DECLARED only: the size fields in the zip headers
are patched, so no test allocates the real bytes.
"""
import base64
import hashlib
import io
import json
import struct
import zlib
import zipfile

MANIFEST = "clark-brand.json"
TOKENS = "tokens.css"
COVER = "assets/cover.png"
LOGO = "assets/logo.png"
BRAND_ID = "example-brand"

MEMBER_CAP = 5 * 1024 * 1024         # a member larger than this is hostile
ZIP_CAP = 16 * 1024 * 1024           # a zip file larger than this on disk is hostile (read_once)
TOTAL_CAP = 24 * 1024 * 1024         # total unpacked size over this is hostile (declared sum AND counted while reading)
FILE_COUNT_CAP = 50                  # entries in the zip: 50 accepted, 51 refused
MEMBER_RATIO = 100                   # a member over RATIO_FLOOR bytes that is more than 100x its compressed size is hostile
RATIO_FLOOR = 64 * 1024
TOTAL_RATIO = 20                     # total unpacked over 20x the total compressed is hostile
COMMENT_CAP = 1024                   # zip comment: 1024 accepted, 1025 refused
TOKENS_CAP = 256 * 1024
PICTURE_CAP = 1024 * 1024            # a PNG over this is refused
RESERVED_IDS = ("assets", "design-system", "generic", "local-brand")
_DATE = (1980, 1, 1, 0, 0, 0)

TOKENS_CSS = b":root {\n  --brand-ink: #1a2b3c;\n  --brand-accent: #c0392b;\n  --brand-paper: #ffffff;\n}\n"


def _chunk(kind, data):
    body = kind + data
    return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)


def _png(colour, width=1, height=1, pad=0):
    """A real PNG of the given (r, g, b); width/height are only written in the header (the pixel data stays 1x1, which is
    all the structure walk reads). pad: bytes of deterministic incompressible text in a tEXt chunk."""
    raw = b"\x00" + bytes(colour)
    out = (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)))
    if pad:
        out += _chunk(b"tEXt", b"Comment\x00" + noise(pad))
    return out + _chunk(b"IDAT", zlib.compress(raw, 9)) + _chunk(b"IEND", b"")


def noise(n):
    """n deterministic bytes of letters and digits that deflate to about 3/4 of their size (hex text deflates to 1/2)."""
    out, i = bytearray(), 0
    while len(out) < n:
        out += hashlib.sha256(b"clark-noise-%d" % i).hexdigest().encode()
        i += 1
    return bytes(out[:n])


COVER_PNG = _png((26, 43, 60))
LOGO_PNG = _png((192, 57, 43))
NOT_A_PICTURE = b"GIF89a\x01\x00\x01\x00\x00\x00\x00;"      # a GIF header, not PNG / JPEG / WebP
# A JPEG: SOI, JFIF, a quantisation table, SOF0 (1 x 1, one component), a Huffman table, SOS, a few scan bytes, EOI.
_DQT = b"\xff\xdb" + struct.pack(">H", 67) + b"\x00" + bytes([1] * 64)
_SOF = b"\xff\xc0" + struct.pack(">H", 11) + b"\x08" + struct.pack(">HH", 1, 1) + b"\x01\x01\x11\x00"
_DHT = b"\xff\xc4" + struct.pack(">H", 20) + b"\x00" + bytes([1] + [0] * 15) + b"\x00"
_SOS = b"\xff\xda" + struct.pack(">H", 8) + b"\x01\x01\x00\x00\x3f\x00"
JPEG = (b"\xff\xd8" + b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        + _DQT + _SOF + _DHT + _SOS + b"\x7f\xa0" + b"\xff\xd9")
JPEG_CUT = JPEG[:-12]                  # ends inside the scan, no EOI
WEBP = base64.b64decode("UklGRhoAAABXRUJQVlA4TA0AAAAvAAAAEAcQERGIiP4HAA==")        # a 1 x 1 lossless WebP
WEBP_WRONG_LENGTH = WEBP[:4] + struct.pack("<I", len(WEBP) + 100) + WEBP[8:]


def valid_members():
    """The members of the valid brand, as {name: bytes}, without the manifest."""
    return {TOKENS: TOKENS_CSS, COVER: COVER_PNG, LOGO: LOGO_PNG}


def full(name, top=BRAND_ID):
    """The member name in the zip for a manifest path."""
    return name[1:] if name.startswith("!") else "%s/%s" % (top, name)


def manifest_for(members, name="Example Brand", version="1.0.0", brand_id=BRAND_ID, modes=None):
    """The manifest dict for members: path, size, sha256 and mode of each, sorted by path."""
    files = [{"path": p, "size": len(b), "sha256": hashlib.sha256(b).hexdigest(),
              "mode": "%04o" % ((modes or {}).get(p) or 0o644)} for p, b in sorted(members.items())]
    return {"id": brand_id, "name": name, "version": version, "files": files}


def manifest_bytes(manifest):
    return json.dumps(manifest, sort_keys=True, indent=2).encode("utf-8") + b"\n"


def _info(name, mode=None, folder=False):
    info = zipfile.ZipInfo(name, _DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (mode if mode is not None else (0o40755 if folder else 0o100644)) << 16
    return info


def zip_name(brand_id=BRAND_ID, version="1.0.0"):
    return "clark-brand-%s-%s.zip" % (brand_id, version)


def build(members=None, manifest=None, order=None, extra=(), modes=None, top=BRAND_ID, brand_id=BRAND_ID, comment=b"",
          folders=(), stored=()):
    """Build a zip. members: {name: bytes} (default: the valid brand). manifest: a dict, bytes, or None for the honest manifest
    of members. top: the one top folder ('' for none). order: member names in write order (default sorted). extra: (name, bytes)
    pairs written after, and NOT put in the manifest (so a duplicate or an unlisted file can be added). modes: {name: unix mode}.
    folders: folder entry names written (not in the manifest). stored: names written uncompressed."""
    members = dict(valid_members() if members is None else members)
    if manifest is None:
        manifest = manifest_for(members, brand_id=brand_id, modes=modes)
    mbytes = manifest if isinstance(manifest, bytes) else manifest_bytes(manifest)
    names = sorted(members) if order is None else list(order)
    nm = (lambda n: full(n, top)) if top else (lambda n: n[1:] if n.startswith("!") else n)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.comment = comment
        z.writestr(_info(nm(MANIFEST)), mbytes)
        for n in names:
            info = _info(nm(n), (modes or {}).get(n))
            if n in stored:
                info.compress_type = zipfile.ZIP_STORED
            z.writestr(info, members[n])
        for n, b in extra:
            z.writestr(_info(nm(n)), b)
        for f in folders:
            z.writestr(_info(f, folder=True), b"")
    return buf.getvalue()


def declare_sizes(data, sizes):
    """Return data with the DECLARED uncompressed size of the named members (full zip names) patched (local and central headers);
    the stored bytes are unchanged, so nothing large is allocated. sizes: {full name: declared size}."""
    out = bytearray(data)
    for sig, off, name_off, hdr in ((b"PK\x01\x02", 24, 46, 46), (b"PK\x03\x04", 22, 30, 30)):
        pos = 0
        while True:
            pos = out.find(sig, pos)
            if pos < 0:
                break
            nlen = struct.unpack_from("<H", out, pos + (28 if sig == b"PK\x01\x02" else 26))[0]
            name = bytes(out[pos + name_off:pos + name_off + nlen]).decode("utf-8", "replace")
            if name in sizes:
                struct.pack_into("<I", out, pos + off, sizes[name])
            pos += hdr
    return bytes(out)


def _patch(data, fn):
    """Call fn(out, kind, pos, name) for every local ('L') and central ('C') header of data (a bytearray copy is returned)."""
    out = bytearray(data)
    for sig, kind, name_off, len_off in ((b"PK\x03\x04", "L", 30, 26), (b"PK\x01\x02", "C", 46, 28)):
        pos = 0
        while True:
            pos = out.find(sig, pos)
            if pos < 0:
                break
            nlen = struct.unpack_from("<H", out, pos + len_off)[0]
            name = bytes(out[pos + name_off:pos + name_off + nlen]).decode("utf-8", "replace")
            fn(out, kind, pos, name)
            pos += 4
    return bytes(out)


def _field(data, target, local_off, central_off, fmt, value):
    """Set one header field of the member with full zip name `target` in both its local and central header."""
    def one(out, kind, pos, name):
        if name == target:
            struct.pack_into(fmt, out, pos + (local_off if kind == "L" else central_off), value)
    return _patch(data, one)


# ---- the valid brand -------------------------------------------------------------------------------------------------

def valid():
    return build()


def valid_jpeg():
    m = valid_members()
    m["assets/cover.jpg"] = JPEG
    return build(m)


def valid_webp():
    m = valid_members()
    m["assets/cover.webp"] = WEBP
    return build(m)


def valid_data_font():
    return _with_tokens(b"@font-face { font-family: x; src: url(data:font/woff2;base64,AAAA); }\n" + TOKENS_CSS)


def with_id(brand_id):
    """A brand whose folder and manifest both say brand_id (use it for the id-rule cases)."""
    return build(brand_id=brand_id, top=brand_id)


def exactly(n):
    """A brand with exactly n entries in the zip (the manifest counts as one)."""
    m = valid_members()
    for i in range(n - 1 - len(m)):
        m["assets/cover-%02d.png" % i] = COVER_PNG
    return build(m)


# ---- hostile variants. Each keeps the manifest honest about what it lists unless the variant is about the manifest. ------

def path_traversal():
    m = valid_members()
    m["!%s/../x" % BRAND_ID] = b"escaped"
    return build(m)


def absolute_path():
    m = valid_members()
    m["!/etc/clark-brand-x"] = b"absolute"
    return build(m)


def drive_letter():
    m = valid_members()
    m["C:evil.png"] = COVER_PNG
    return build(m)


def backslash_path():
    m = valid_members()
    m["assets\\logo2.png"] = COVER_PNG
    return build(m)


def symlink_member():
    m = valid_members()
    m["assets/link.png"] = b"/etc/passwd"
    return build(m, modes={"assets/link.png": 0o120777})


def odd_mode(mode):
    return build(modes={COVER: mode})


def not_unix():
    """Every member made on a non-Unix system (create_system 0)."""
    return _patch(build(), lambda out, kind, pos, name: struct.pack_into("<B", out, pos + 5, 0) if kind == "C" else None)


def link_dir_entry():
    """A folder entry (name ends '/') as a Finder zip has."""
    return build(folders=[BRAND_ID + "/assets/"])


def member_over_cap():
    """assets/big.png declares 5 MB + 1 (header only; the stored bytes are tiny)."""
    m = valid_members()
    m["assets/big.png"] = COVER_PNG
    return declare_sizes(build(m), {full("assets/big.png"): MEMBER_CAP + 1})


def too_many_files():
    m = valid_members()
    for i in range(FILE_COUNT_CAP + 19):
        m["assets/cover-%03d.png" % i] = COVER_PNG
    return build(m)


def total_unpacked_declared():
    """Five members each under the member cap whose DECLARED sizes sum to more than 24 MB (header only). (Each also declares
    far more than 100x its compressed size: all the refusals are the same one, the damaged-file refusal.)"""
    m = valid_members()
    sizes = {}
    for i in range(5):
        n = "assets/cover-%d.png" % i
        m[n] = COVER_PNG
        sizes[full(n)] = MEMBER_CAP - 1
    return declare_sizes(build(m), sizes)


def bomb_ratio(size=200 * 1024):
    """tokens.css is size bytes of spaces (more than 100x its compressed size), padded elsewhere so the TOTAL ratio stays low."""
    m = valid_members()
    m[TOKENS] = TOKENS_CSS + b" " * (size - len(TOKENS_CSS))
    m[COVER] = _png((26, 43, 60), pad=size)
    return build(m)


def small_member_high_ratio():
    """A tokens.css of 60 KB (64 KB or smaller) at far over 100x: allowed. The total ratio stays under 20."""
    return bomb_ratio(60 * 1024)


def total_ratio():
    """Four members of 60 KB each (each allowed alone at over 100x); together over 20x the total compressed size."""
    m = valid_members()
    for i in range(4):
        m["assets/cover-%d.png" % i] = b"\x00" * (60 * 1024)
    return build(m)


def stream_longer_than_declared():
    """assets/cover.png declares 100 bytes but its deflate stream expands to 4 MB of zeros (the manifest says 4 MB, honestly)."""
    m = valid_members()
    m[COVER] = b"\x00" * (4 * 1024 * 1024)
    return declare_sizes(build(m), {full(COVER): 100})


def lying_total():
    """Six members each declaring 1000 bytes (the central directory sums to a few KB) whose real bytes are 4 MB of zeros each."""
    m = valid_members()
    sizes = {}
    for i in range(6):
        n = "assets/cover-%d.png" % i
        m[n] = b"\x00" * (4 * 1024 * 1024)
        sizes[full(n)] = 1000
    return declare_sizes(build(m), sizes)


def encrypted():
    """The cover's flag_bits has bit 0 (encrypted) in the local and central headers."""
    return _field(build(), full(COVER), 6, 8, "<H", 0x1)


def method_99():
    return _field(build(), full(COVER), 8, 10, "<H", 99)


def method_12():
    return _field(build(), full(COVER), 8, 10, "<H", 12)


def zip64():
    """The cover's central-directory compressed size is at the zip64 sentinel 0xFFFFFFFF."""
    return _field(build(), full(COVER), 18, 20, "<I", 0xFFFFFFFF)


def overlapping():
    """The logo's central-directory offset points at the cover's local header."""
    data = build()
    offs = {}
    _patch(data, lambda out, kind, pos, name: offs.__setitem__(name, pos) if kind == "L" else None)
    def one(out, kind, pos, name):
        if kind == "C" and name == full(LOGO):
            struct.pack_into("<I", out, pos + 42, offs[full(COVER)])
    return _patch(data, one)


def long_comment(n=COMMENT_CAP + 1):
    return build(comment=b"x" * n)


def sha_mismatch():
    m = valid_members()
    man = manifest_for(m)
    man["files"][0]["sha256"] = "0" * 64
    return build(m, manifest=man)


def size_mismatch():
    m = valid_members()
    man = manifest_for(m)
    man["files"][0]["size"] += 1
    return build(m, manifest=man)


def manifest_missing_file():
    """The zip holds assets/logo.png but the manifest does not list it."""
    m = valid_members()
    man = manifest_for(m)
    man["files"] = [f for f in man["files"] if f["path"] != LOGO]
    return build(m, manifest=man)


def row_without_file():
    man = manifest_for(valid_members())
    man["files"].append({"path": "assets/cover-9.png", "size": 1, "sha256": "0" * 64, "mode": "0644"})
    return build(manifest=man)


def extra_file_not_in_manifest():
    return build(valid_members(), extra=[("assets/extra.png", COVER_PNG)])


def manifest_edit(**changes):
    """The honest manifest with the given top-level keys replaced (a value of None removes the key)."""
    man = manifest_for(valid_members())
    for k, v in changes.items():
        if v is None:
            man.pop(k, None)
        else:
            man[k] = v
    return build(manifest=man)


def manifest_raw(raw):
    return build(manifest=raw)


def manifest_deep():
    return manifest_raw(b'{"id": "' + BRAND_ID.encode() + b'", "x": ' + b"[" * 5000 + b"]" * 5000 + b"}")


def manifest_long_int():
    return manifest_raw(b'{"id": "%s", "name": "n", "version": "1.0.0", "files": [], "x": %s}' % (BRAND_ID.encode(), b"9" * 5000))


def id_differs():
    """The manifest id is not the folder's."""
    return manifest_edit(id="other-brand")


def two_top_folders():
    return build(extra=[("!other/readme.txt", b"x")])


def no_top_folder():
    return build(top="")


def duplicate_names():
    """assets/logo.png appears twice (the second copy is not in the manifest)."""
    return build(valid_members(), extra=[(LOGO, COVER_PNG)])


def case_clash():
    """assets/Logo.png and assets/logo.png differ only in case."""
    m = valid_members()
    m["assets/Logo.png"] = COVER_PNG
    return build(m)


def _with_tokens(css):
    m = valid_members()
    m[TOKENS] = css
    return build(m)


def tokens_with_url():
    return _with_tokens(b":root { --brand-bg: url(http://example.invalid/x.png); }\n")


def tokens_with_picture_url():
    return _with_tokens(b":root { --brand-bg: url(data:image/png;base64,AAAA); }\n")


def tokens_with_import():
    return _with_tokens(b"@import 'http://example.invalid/x.css';\n:root { --brand-ink: #000000; }\n")


def tokens_with_rules():
    return _with_tokens(b":root { --brand-ink: #000000; }\nbody { display: none; }\n")


def tokens_import_url_font():
    return _with_tokens(b"@font-face { font-family: x; src: url(http://example.invalid/x.woff2); }\n" + TOKENS_CSS)


def tokens_style_close():
    return _with_tokens(b":root { --brand-ink: #000000; }\n/* </style><script>x</script> */\n")


def tokens_not_utf8():
    return _with_tokens(b":root { --brand-ink: \xff\xfe; }\n")


def tokens_of_size(n):
    """A tokens.css of exactly n bytes (a comment of incompressible text), valid otherwise."""
    pad = n - len(TOKENS_CSS) - 5
    return _with_tokens(TOKENS_CSS + b"/*" + noise(pad) + b"*/\n")


def tokens_over_256k():
    return tokens_of_size(TOKENS_CAP + 1)


def tokens_at_256k():
    return tokens_of_size(TOKENS_CAP)


def tokens_over_1mb():
    return tokens_of_size(1024 * 1024 + 1)


def tokens_with_word(word):
    return _with_tokens(b":root { --brand-ink: #000000; --brand-note: " + word.encode() + b"; }\n")


def not_a_picture():
    """assets/cover.png is named .png but its bytes are a GIF."""
    m = valid_members()
    m[COVER] = NOT_A_PICTURE
    return build(m)


def png_bad_crc():
    bad = bytearray(COVER_PNG)
    bad[29] ^= 0xFF                      # a byte of the IHDR check value
    m = valid_members()
    m[COVER] = bytes(bad)
    return build(m)


def png_over_1mb():
    m = valid_members()
    m[COVER] = _png((26, 43, 60), pad=PICTURE_CAP)
    return build(m)


def png_too_wide():
    """Header says 2001 x 1 (for the Excel files the most is 2000 pixels a side)."""
    m = valid_members()
    m[LOGO] = _png((192, 57, 43), width=2001)
    return build(m)


def jpeg_cut_short():
    m = valid_members()
    m["assets/cover.jpg"] = JPEG_CUT
    return build(m)


def webp_wrong_length():
    m = valid_members()
    m["assets/cover.webp"] = WEBP_WRONG_LENGTH
    return build(m)


def name_outside_list():
    m = valid_members()
    m["assets/payload.exe"] = b"MZ"
    return build(m)


def denied_name(word):
    """An ALLOWED file name that holds a deny-list word (so only the deny-list can refuse it). The word comes from brands."""
    m = valid_members()
    m["assets/logo-%s.png" % word] = COVER_PNG
    return build(m)


def denied_brand_name(word):
    return build(manifest=manifest_for(valid_members(), name="Brand %s" % word))


HOSTILE = {builder.__name__: builder for builder in (
    path_traversal, absolute_path, drive_letter, symlink_member, member_over_cap, too_many_files, total_unpacked_declared,
    sha_mismatch, size_mismatch, manifest_missing_file, row_without_file, extra_file_not_in_manifest, tokens_with_url,
    tokens_with_import, tokens_with_rules, not_a_picture, backslash_path, duplicate_names, case_clash, bomb_ratio, total_ratio,
    stream_longer_than_declared, lying_total, encrypted, method_99, method_12, zip64, overlapping, long_comment, link_dir_entry,
    not_unix, png_bad_crc, png_over_1mb, png_too_wide, jpeg_cut_short, webp_wrong_length, tokens_over_256k, tokens_over_1mb,
    tokens_import_url_font, tokens_style_close, tokens_not_utf8, tokens_with_picture_url, id_differs, two_top_folders,
    no_top_folder, name_outside_list, manifest_deep, manifest_long_int,
)}
