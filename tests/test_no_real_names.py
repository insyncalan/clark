"""No real client, company, project or people names in the repository (#29; "in creaite we have a rule
that's enforced that ensures that all publically posted repos hold mock up customer information - review creaite and
implement same for clark").

Copied from creaite v2.6.11 (1c192ce) dev/tests/test_no_real_names.py, with its banned hashes. clark's examples, mockups,
tests and docs use fictional data only. This scans every tracked file (`git ls-files`, skipping vendored libraries and
binary files) and every tracked path, and fails if any word, or any two-word phrase, matches a banned name. The banned
names are stored only as SHA-256 hashes of the lower-cased name, so this file never publishes them. It never skips and
needs no local file, so it runs the same in every checkout and worktree.

clark adds to creaite's check (creaite skips Office files; clark mustn't):
- the parts inside a .docx, .xlsx, .pptx or .zip are read too; a part that can't be read is reported, never skipped;
- each text is also read with its tags removed and with each tag as a space, entities decoded, so a name split across a
  .docx's runs, or broken by <w:br/>, a line break or a non-breaking space, is still found;
- words are NFC-normalised and case-folded, and also read with their accents removed ("Nórthwind" as "northwind");
- two-word phrases in paths are checked too;
- text saved as UTF-16 (a byte-order mark, or many NULs) is decoded and read, not skipped as binary;
- zips inside zips (a .docx holding a .zip) are read to four levels and 64 MB; deeper or bigger is reported, never skipped;
- an invisible format character inside a word (a zero-width space, a soft hyphen, a joiner) is read both removed and as a
  space, so "North\u00adwind" and "Zoe\u200bQuill" are still found.
A hit names the file only by its place in `git ls-files` (find it with: git ls-files | sed -n '<i>p') and a part by its
number, never by a path or part name, and never prints a hash.

To ban another name, add the hash of its lower-cased form (one word, or two words separated by one space):
    python3 -c "import hashlib;print(hashlib.sha256(b'name').hexdigest())"

Run: python3 dev/run_tests.py test_no_real_names
"""
import hashlib
import html
import io
import re
import subprocess
import unicodedata
import unittest
import zipfile

from _paths import ROOT

BANNED = frozenset({
    "97a6eb426111984bea4e6346d4381bf7265c1acb864ff88aa65e3cacbf698d9e",
    "e192cd5626a00f0dfd97cee3d5d99b64972a8c161c31bec2c67395e68a6adca4",
    "aaadc31b1826c3b92a9fb03cb28c0f06110f82942877a040acebb8604937ba12",
    "cc446d5e475fe2936f5089841eaf6d13618b57625be8437021e156518e596418",
    "674cc4ad17541df15983acc98b40f1ecab771c69c30efc09916c24fef90b150a",
    "6aff1bb1b50525063ad48e222220a50a0c47374eea325abd5533c979ba204191",
    "ac2c6f6fc9cdd1ccb1bc307070396eab61f5bcbdb98c3b9b1f7c930b14c422c3",
    "60bd7fd2ab7e986e85355c8011d197aa4d97c3956352aa32cc6d94b5b92df295",
    "704d45f5fa2b893677831d0394693e388e9826de155a5d29f77472397229bdae",
    "33ec6ed7a20fab8d7207db970a9308768473be8b64d59277a2b30f6524584a6e",
    "64d68806ef56ee71e8b59e7f19bc50fee515ed11e1ebd6dbda5a109f4fd75356",
    "8aed32fd8a238520301c00b64ad98b2f18295efb2dc53bbc6e27c92c3fdb162c",
    "b32f52bf59a62214b66a6d6769611b7e7c2c5361cb940d54874c64a4189692e9",
    "1c7272b3cb1d980b7701040e8afd537af886a437cd718ffdaf7c49c41171e11c",
    "bdaf2f8d04cea26aa546876b1e27b3e4db96a524a128dd033745b2de5a5c175a",
    "e4bb33e05498befc02052011b9a04bcb4eb99006088fcea77fc829385430f288",
    "c932bc96718c66e1dfea8f9432471e296a81d33c1fd0d3970ed7f87e57bb2459",
    "4b7bb8c301065be38ebed64ed1e85e4ef6f6a06210b6c29abc5919619819b7c0",
    "160a5c716369cdb64d13e8f4cf6ee75f1cf7d70c2252a75d50f86223835716d6",
    "3b9b21b853639a9b7c1ce503095776aba9c567961c27a665a3cd87702a8acc3d",
    "4ec0fd7916e201d92f7ba220d13f227794d2c37fd91b8d5c733c0491e71d53a6",
    "2b98fb6954368ff3f28f3367b697c1ae3b3d1e69b82a5de92b58a5e40993bbe0",
    "e52b22b4438ef532d7f816216eb50de1ac9ea7646bcf2d356ac6eac6f4abe013",
    "8b4bbb2e1aa22e7a50140affbd254bc86bdffcd3c1700e57b00282e1cb1b9c33",
    "2ebae47bc84f5cc5a86d5de2cf3508720acedd2e30f1595c028412bd5eacbb0f",
    "3343cd126b042f8d61c1c3cdcf543926d3f67c1354a703662a8e7292c77b03f9",
    "d6e2ded0c7a3fba5aea5494d699088f14bd6fca977fe8f6dc44c3b7a3665e1f6",
    "3a22797258870f8ca0a9c898e29b9e5d08f76d65302c3794d322590808944e2c",
    "3a8ce1b9a36dd74a795466108fc8c285d7715ddc716254fef017afd003777774",
    "be53aa7b1e2d707d139b6a4cab9efc5dcdedd730bd649b504555736d955f2301",
    "319ec3e742d3a04898f95a619fe42172baba030c0c00c5deb32968108ffa41e4",
    "6459067ae461097b1099d067b577b600bd4da33315a3645801cc82034dd60fb2",
    "9fe03ea331bba94a4369f1c82cf0981fe401dda25c26a9b2abbb9c242e7a4ebd",
    "0e16af977ef0e07a117d91be07452c6ee2e306347eaf1e14aca1b1454f0af846",
    "ec6a13b802f63ae75d26f5635297a1c725b5ad6f2489fd229f77661ff80602f0",
    "626858e017b57b84c2c082ba464c4e9179e65647c23ed0ea9c6926bdb753f599",
    "8b09cc07d943ee9d68dd3e53d34b09b88779427e9b3013fa9111f41cc74baa6b",
    "22f83076aa7a9955ce280140369a92974477e316c2bf997dc8e1390d9432fc6c",
    "0336dbe2578e59a7c2a60320d17134a11ea91f5011c94b92124bc1ddfb9a1c95",
    "04cc0d053c4e13fa19b6d40a29a2249b81da6b49b6184eb2ff68ce80a8dae448",
    "091058149ada9d0ca2a947ccc080e0518ec130ebdec91d744ca9c99a5b5f2483",
    "0a9da0bf03c554a94c8190bedefd4c27101ba66130cfd566ea6bc8dc230e6020",
    "0d16fd5a06a36dc2b4401b5b42384385f462dc9df6a8a546216644826e7a8795",
    "1986f2a454c359c01a7ce069e21a97fa0c2b19220fe78f6d601d0e6d4211bce3",
    "1d11af386066b39e14a2bf40516721c35df6a1c76dc44bc3de28d48c4a5f504d",
    "2bac1e271bcea539b42151430976779ee7347997175004c7bd27b0b532034bdf",
    "3c4a8084fdf78ebb945084513f51830a486eac1ae25b9108d6fbb6be17aa73f5",
    "4599e9690ccbf191811ab4e3320bf28795a1ae47d8837e3093c3314ba784cafd",
    "4924fe304a4f2db79215c638d2ef985d50adeb4b4820d2f473dbb656e8bc7881",
    "4f0dc8530cfce5ad1cffc3b2a6d4aa18da546a866648c4dd2283a444382299f3",
    "4f19a54e5bcf5a0c6e698c6a64920392c5ce1e2c6f02684130c6f4a0fbdddc8d",
    "4ffb660d6028b4141f1def3e7c577703a2ae735e30bbdd5ef25b8316737957ab",
    "62957b490c255479f27e819d2f0f737343044e0cdd17d413a6da4e760296e4c2",
    "63ea73f7900385a8a01edbde182006fed16f7e06fc8961d0497f86b7a4b7f031",
    "674cc4ad17541df15983acc98b40f1ecab771c69c30efc09916c24fef90b150a",
    "715b82d8e0274cd97904c0c2f2deae68046c904cb9b86a199df2c7e215a40df2",
    "7196a7d7ac20f1419249c21ade9bc8ef5a41e21034dac2e00df9f2c24b7fff5b",
    "7cf327578ac45c3eea6b8c114cb0f6013dd5561242f9a073a0b22f4b93ed8636",
    "823de393b3aad60b7fbd8e42327369d33367d4cbae726ff5a949abada8871574",
    "82d195784ad7f39ca9eb27c7ba5811600a203ec90f916795b264065f36bb88bb",
    "91bb70e9cb371cf298a86c2fd161f39e6112fb33fd1336071e450f61315f18b0",
    "96b6bda370f865178c13520f96c3280faa645ad8a543553b027db8a4916fc29c",
    "9a51431f385960b25218b88e4f7449168b2706f5d47144291dbeede351818b9d",
    "a3dd2c2d24923f6b7bb18d6f39f8f041e212699dc0f07a6be26fa6101622a6b7",
    "b0cad320c1040ef8459ecaa45e0cbf26d1dc8e670498771b9129d8aaaa930d5f",
    "b735f5177e46861969f9086b8f00ef20f2c09c0ec435204c3f3ad90938a4a1c1",
    "bfd2184c211d481fc04e40bf48d2afe78cde6b8e456d2879932135c74f7686d9",
    "c31ddcd13c478950387c985a4400372ac271dfbee3003ab86646f7f51b5e9f9b",
    "dce90f5d6d335259c9d6e62f08325906973348abe4973b757266691c652245b5",
    "dfed50be604752cc39631701b461d27802d61ecc59b2c107b399af2e974de6b1",
    "e0a0d31dd907719084eb88a2e42d6d6c81b91c20d63d4c22e9fb338b9252e6fc",
    "e891798bd628928b16ba8b820f905360f33829bed2269b64e34bf2ebbf7f855e",
    "ee24119361c62ca2e35900466836b9358de4836538cd3552bdca005bbaf5bc13",
    "f44c66b093311d3086a8c34cc56f91638df5c810203e90046f46d14a72d3c0d0",
    "f7a168eb3648797c090912937c7f6cbf0589ed57932eb21cc30dbaf4c537a200",
    "f82f94aeea657935366f8e742e6c20c3aa9d97068ea27b5656e8023a8aa3cef0",
    "fc6f64b1e383aee49803b01dc83274cd1fc25b980aeb2ff1ce894c80b3c0ebba",
})

WORD = re.compile(r"[a-z0-9]+")
DOMAIN = re.compile(r"@([a-z0-9-]+(?:\.[a-z0-9-]+)+)")
SKIP = re.compile(r"(^|/)vendor/|\.(png|jpe?g|gif|ic(?:o|ns)|pdf|gz|woff2?|ttf|otf|db|sqlite)$", re.I)
TAG = re.compile(r"<[^>]*>")


def digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def tracked(repo=ROOT):
    """[(place in git ls-files, path)] for every tracked file the check reads."""
    out = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"], capture_output=True, check=True).stdout
    return [(i, p) for i, p in enumerate(out.decode("utf-8").split("\0"), 1) if p and not SKIP.search(p)]


def forms(text):
    """`text` NFC-normalised and case-folded, and the same with its accents removed (both when they differ). When it holds
    invisible format characters (zero-width space, soft hyphen, joiners: category Cf) it is also read with them removed and
    with each as a space."""
    base = unicodedata.normalize("NFC", text)
    variants = [base]
    if not base.isascii() and any(unicodedata.category(c) == "Cf" for c in base):
        variants = ["".join(c for c in base if unicodedata.category(c) != "Cf"),
                    "".join(" " if unicodedata.category(c) == "Cf" else c for c in base)]
    out = []
    for variant in variants:
        folded = variant.casefold()
        bare = "".join(c for c in unicodedata.normalize("NFKD", folded) if not unicodedata.combining(c))
        for f in ([folded] if bare == folded else [folded, bare]):
            if f not in out:
                out.append(f)
    return out


def banned_words(words, banned):
    """Whether any word, or any pair of neighbouring words, is banned."""
    return any(digest(w) in banned or (i + 1 < len(words) and digest(f"{w} {words[i + 1]}") in banned)
               for i, w in enumerate(words))


def banned_domain(domain, banned=None):
    """An email domain is banned when the whole of it, or the part before its last dot, or any one part is."""
    banned = BANNED if banned is None else banned
    parts = domain.split(".")
    return any(digest(x) in banned for x in (domain, ".".join(parts[:-1]), *parts))


def banned_in(text, banned=None):
    """Line numbers with a hit: each word, each pair of neighbouring words and each email domain, in each form."""
    banned = BANNED if banned is None else banned
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        for f in forms(line):
            if any(banned_domain(d, banned) for d in DOMAIN.findall(f)) or banned_words(WORD.findall(f), banned):
                hits.append(n)
                break
    return hits


def banned_across(text, banned=None):
    """Whether a name is found only when the text is read whole, with tags removed or read as spaces and entities
    decoded: a name split across runs, tags or lines."""
    banned = BANNED if banned is None else banned
    for gap in ("", " "):
        for f in forms(html.unescape(TAG.sub(gap, text))):
            if banned_words(WORD.findall(f), banned):
                return True
    return False


def text_of(data):
    """The text of `data`, or None for a binary file. Text saved as UTF-16 (a byte-order mark, or a quarter or more of the
    bytes NUL, which is what ASCII text looks like in UTF-16) is decoded; a zip is never read as text."""
    if b"\0" not in data:
        return data.decode("utf-8", "ignore")
    if data[:2] == b"PK":
        return None
    if data[:2] == b"\xff\xfe":
        return data.decode("utf-16-le", "ignore")
    if data[:2] == b"\xfe\xff":
        return data.decode("utf-16-be", "ignore")
    if data.count(b"\0") * 4 >= len(data):
        little = data[1::2].count(b"\0") > data[0::2].count(b"\0")
        return data.decode("utf-16-le" if little else "utf-16-be", "ignore")
    return None


MAX_ZIP_DEPTH = 4                       # zips inside zips inside a .docx; deeper than this is reported, not skipped
MAX_ZIP_BYTES = 64 * 1024 * 1024        # everything unpacked from one file, all levels together


def parts(data, budget=None):
    """(part number, part name, bytes or None) for each part of a zip (.docx, .xlsx, .pptx); None when it can't be read
    (or would take more than the `budget` of bytes, a one-item list, that is left for this file)."""
    if data[:2] != b"PK":
        return
    budget = [MAX_ZIP_BYTES] if budget is None else budget
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for j, info in enumerate([i for i in z.infolist() if not i.is_dir()], 1):
                try:
                    if info.file_size > budget[0]:
                        raise ValueError("too big")
                    budget[0] -= info.file_size
                    yield j, info.filename, z.read(info)
                except Exception:  # noqa: BLE001  encrypted, an unsupported compression, damaged
                    yield j, info.filename, None
    except zipfile.BadZipFile:
        yield 0, "", None                                   # a damaged zip: the whole file can't be read


def name_banned(name, banned):
    return any(digest(f) in banned or banned_words(WORD.findall(f), banned) for f in forms(name))


def text_hits(at, text, banned):
    lines = banned_in(text, banned)
    out = [f"{at} line {n}" for n in lines]
    if not lines and banned_across(text, banned):
        out.append(f"{at} across tags or lines")
    return out


def part_hits(base, data, banned, depth, budget):
    """Findings for the parts of a zip, and for zips inside it (to MAX_ZIP_DEPTH levels): 'tracked file #3 part #2.1 ...'.
    A part that can't be read, or a zip nested too deep, is a finding."""
    found = []
    for j, name, part in parts(data, budget):
        if j == 0:
            if text_of(data) is None:                        # a damaged zip that isn't text either
                found.append(f"{base} can't be read, so it can't be checked")
            continue
        part_at = f"{base} part #{j}" if depth == 1 else f"{base}.{j}"
        if name_banned(name, banned):
            found.append(f"{part_at} (its name)")
        if part is None:
            found.append(f"{part_at} can't be read, so it can't be checked")
            continue
        text = text_of(part)
        if text is not None:
            found += text_hits(part_at, text, banned)
        if part[:2] == b"PK":
            if depth >= MAX_ZIP_DEPTH:
                found.append(f"{part_at} is nested too deep, so it can't be checked")
            else:
                found += part_hits(part_at, part, banned, depth + 1, budget)
    return found


def findings(repo=ROOT, banned=None):
    """Every place a banned name is found, by place in `git ls-files` (and part number) only."""
    banned = BANNED if banned is None else banned
    found = []
    for i, path in tracked(repo):
        at = f"tracked file #{i}"
        if name_banned(path, banned):
            found.append(f"{at} (its name)")
        try:
            data = (repo / path).read_bytes()
        except (FileNotFoundError, IsADirectoryError):
            continue
        except OSError:                                      # PermissionError and the like: its message names the path
            found.append(f"{at} can't be read, so it can't be checked")
            continue
        text = text_of(data)
        if text is not None:
            found += text_hits(at, text, banned)
        found += part_hits(at, data, banned, 1, [MAX_ZIP_BYTES])
    return found


class NoRealNames(unittest.TestCase):
    def test_the_check_itself(self):
        self.assertEqual(len(BANNED), len(set(BANNED)))
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{64}", h) for h in BANNED))
        self.assertEqual(banned_in("Jane Doe and Omar Ali, ABC Example Programme, jane.doe@client.com"), [])
        self.assertFalse(banned_domain("brightwater.example"))

    def test_no_tracked_file_names_a_real_client_project_or_person(self):
        self.assertEqual(findings(), [], "a real name (by its hash) is in these places; use the fictional sample data "
                                         "instead (find a file with: git ls-files | sed -n '<n>p')")

    def test_committed_files_name_no_client(self):
        """The two looks' names and the client's name are on the banned list (no client logo, name or picture in clark). Only their
        digests are written here, so this file never holds a name, split or whole; and a tracked file that carries a banned name, in its text or its
        path, fails the check, tried with a made-up name added to the list for this test only."""
        import tempfile
        from pathlib import Path
        asked_for = ("cc446d5e475fe2936f5089841eaf6d13618b57625be8437021e156518e596418", "674cc4ad17541df15983acc98b40f1ecab771c69c30efc09916c24fef90b150a",
                     "97a6eb426111984bea4e6346d4381bf7265c1acb864ff88aa65e3cacbf698d9e", "f44c66b093311d3086a8c34cc56f91638df5c810203e90046f46d14a72d3c0d0")
        for h in asked_for:
            self.assertIn(h, BANNED, "a client or look name is on the banned list")
        planted = frozenset(BANNED | {digest("northwind")})                     # a made-up name, for this test only
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "-C", tmp, "init", "-q"], check=True)
            (root / "notes.md").write_text("fine\nthe NORTHWIND look\n", encoding="utf-8")
            (root / "the-northwind-file.css").write_text("a { color: red }", encoding="utf-8")
            subprocess.run(["git", "-C", tmp, "add", "."], check=True)
            found = findings(root, planted)
            self.assertTrue(any("line 2" in f for f in found), f"a name in a file's text was not found: {found}")
            self.assertTrue(any("(its name)" in f for f in found), f"a name in a file's path was not found: {found}")


FICTIONAL = frozenset(digest(n) for n in ("northwind", "northwind traders", "zoë quill", "zoe quill", "quill",
                                          "fabrikam.example", "contoso bank"))


class TheExtraPasses(unittest.TestCase):
    """clark's passes, tried with fictional banned names in a temporary repo."""

    def repo(self, files):
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        subprocess.run(["git", "-C", str(root), "init", "-q"], check=True)
        for name, data in files.items():
            (root / name).parent.mkdir(parents=True, exist_ok=True)
            (root / name).write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
        subprocess.run(["git", "-C", str(root), "add", "."], check=True)
        return root

    @staticmethod
    def office(xml, name="word/document.xml", compress=zipfile.ZIP_DEFLATED):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compress) as z:
            z.writestr(name, xml)
        return buf.getvalue()

    def test_lines_case_unicode_and_domains(self):
        root = self.repo({"a.md": "fine\nOwner: ZOË QUILL\n", "b.md": "zöé".replace("é", "e") + " x",
                          "c.md": "mail ops@Fabrikam.example today", "d.md": "Nórthwind Tráders", "e.md": "clean"})
        self.assertEqual(findings(root, FICTIONAL), ["tracked file #1 line 2", "tracked file #3 line 1",
                                                     "tracked file #4 line 1"])

    def test_office_parts_split_runs_and_tags_as_spaces(self):
        runs = ('<w:r><w:t>Prepared for North</w:t></w:r><w:r><w:t>wind</w:t></w:r>'
                '<w:r><w:t xml:space="preserve"> Traders</w:t></w:r>')
        root = self.repo({"a.docx": self.office(runs), "b.docx": self.office("<w:t>North</w:t><w:br/><w:t>wind</w:t>"),
                          "c.xlsx": self.office("<t>Northwind&nbsp;x</t>", "xl/sharedStrings.xml"),
                          "d.html": "<p>Contoso\nBank</p>", "e.docx": self.office("<w:t>fine</w:t>")})
        self.assertEqual(findings(root, FICTIONAL), ["tracked file #1 part #1 across tags or lines",
                                                     "tracked file #2 part #1 across tags or lines",
                                                     "tracked file #3 part #1 line 1",
                                                     "tracked file #4 across tags or lines"])

    def test_paths_and_part_names_are_checked_and_never_printed(self):
        root = self.repo({"docs/Northwind_Traders-report.md": "fine", "NorthwindTraders.md": "fine",
                          "x/zoe-quill.txt": "fine", "f.zip": self.office("fine", "media/Northwind.png", zipfile.ZIP_STORED)})
        got = findings(root, FICTIONAL)
        self.assertEqual(got, ["tracked file #2 (its name)", "tracked file #3 part #1 (its name)",
                               "tracked file #4 (its name)"])
        printed = " ".join(got).lower()
        for word in ("northwind", "zoe", "quill", ".md", ".zip", "media", "docs"):
            self.assertNotIn(word, printed)
        self.assertNotRegex(printed, r"[0-9a-f]{64}")

    def test_a_part_that_can_t_be_read_is_reported(self):
        def broken(flag=0, method=None):
            data = bytearray(self.office("<t>x</t>", "secret.xml", zipfile.ZIP_STORED))
            for sig, flag_at, method_at in ((b"PK\x03\x04", 6, 8), (b"PK\x01\x02", 8, 10)):
                at = data.find(sig)
                data[at + flag_at] |= flag
                if method is not None:
                    data[at + method_at:at + method_at + 2] = method.to_bytes(2, "little")
            return bytes(data)

        root = self.repo({"a.xlsx": broken(flag=1), "b.xlsx": broken(method=99)})
        self.assertEqual(findings(root, FICTIONAL), ["tracked file #1 part #1 can't be read, so it can't be checked",
                                                     "tracked file #2 part #1 can't be read, so it can't be checked"])

    def test_a_damaged_zip_or_an_unreadable_file_is_reported_by_number(self):
        import os
        damaged = self.office("<t>x</t>")[:40] + b"\0" * 10
        root = self.repo({"a.docx": damaged, "b.md": "Northwind"})
        os.chmod(root / "b.md", 0)
        self.addCleanup(os.chmod, root / "b.md", 0o644)
        got = findings(root, FICTIONAL)
        self.assertEqual(got, ["tracked file #1 can't be read, so it can't be checked",
                               "tracked file #2 can't be read, so it can't be checked"])

    def test_vendored_and_binary_files_are_skipped(self):
        root = self.repo({"vendor/lib.py": "# Northwind", "logo.png": "Northwind", "bin.dat": b"Northwind\0"})
        self.assertEqual(findings(root, FICTIONAL), [])

    def test_utf16_files_are_read(self):
        line = "fine\nOwner: Northwind\n"
        root = self.repo({"a.txt": line.encode("utf-16"), "b.txt": line.encode("utf-16-le"), "c.txt": line.encode("utf-16-be"),
                          "d.txt": b"\xfe\xff" + line.encode("utf-16-be"), "e.txt": "clean\n".encode("utf-16"),
                          "f.docx": self.office(line.encode("utf-16"), "word/document.xml")})
        self.assertEqual(findings(root, FICTIONAL), ["tracked file #1 line 2", "tracked file #2 line 2",
                                                     "tracked file #3 line 2", "tracked file #4 line 2",
                                                     "tracked file #6 part #1 line 2"])

    def test_a_zip_inside_a_docx_is_read(self):
        inner = self.office("<w:t>Prepared for North</w:t><w:t>wind</w:t>", "word/document.xml")
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, "w") as z:
            z.writestr("word/document.xml", "<t>fine</t>")
            z.writestr("word/embeddings/inner.docx", inner)
            z.writestr("word/embeddings/Northwind.zip", self.office("fine", "x.xml", zipfile.ZIP_STORED))
        root = self.repo({"a.docx": outer.getvalue()})
        got = findings(root, FICTIONAL)
        self.assertEqual(got, ["tracked file #1 part #2.1 across tags or lines", "tracked file #1 part #3 (its name)"])
        self.assertNotIn("northwind", " ".join(got).lower())

    def test_nested_zips_have_a_depth_cap_and_a_size_cap(self):
        data = b"Northwind"
        for _ in range(MAX_ZIP_DEPTH + 1):
            data = self.office(data, "inner.zip")
        root = self.repo({"a.zip": data})
        got = findings(root, FICTIONAL)
        self.assertEqual(len(got), 1, got)
        self.assertIn("nested too deep", got[0])
        import test_no_real_names as me
        flat = self.office("Northwind", "a.txt")
        root = self.repo({"b.zip": flat})
        old = me.MAX_ZIP_BYTES
        self.addCleanup(setattr, me, "MAX_ZIP_BYTES", old)
        me.MAX_ZIP_BYTES = 3
        self.assertEqual(me.findings(root, FICTIONAL), ["tracked file #1 part #1 can't be read, so it can't be checked"])

    def test_an_invisible_character_inside_a_name_does_not_hide_it(self):
        zwsp, soft, joiner, bom = "\u200b", "\u00ad", "\u200d", "\ufeff"
        root = self.repo({"a.md": "x\nNorth" + soft + "wind\n", "b.md": "Zoe" + zwsp + "Quill",
                          "c.md": "North" + joiner + "wind Traders", "d.md": "Fabrikam" + zwsp + ".example",
                          "e.md": "plain words", "f.md": "N" + zwsp + "o" + soft + "rthwind",
                          "g.docx": self.office("<w:t>North" + zwsp + "wind</w:t>")})
        self.assertEqual(findings(root, FICTIONAL), ["tracked file #1 line 2", "tracked file #2 line 1",
                                                     "tracked file #3 line 1", "tracked file #6 line 1",
                                                     "tracked file #7 part #1 line 1"])
        self.assertEqual(banned_in("a" + zwsp + "b c" + bom, FICTIONAL), [])
        self.assertIn(1, banned_in("zoe" + zwsp + "quill", FICTIONAL))
        root = self.repo({"North" + soft + "wind.md": "fine", "a" + zwsp + "-quill.txt": "fine"})
        self.assertEqual(findings(root, FICTIONAL), ["tracked file #1 (its name)", "tracked file #2 (its name)"])

    def test_binary_files_that_are_not_utf16_are_still_skipped(self):
        root = self.repo({"bin.dat": b"Northwind" + b"\xff\x01\x02" * 30 + b"\0", "p.docx": b"PK" + b"\0" * 40})
        self.assertEqual(findings(root, FICTIONAL), ["tracked file #2 can't be read, so it can't be checked"])


if __name__ == "__main__":
    unittest.main()
