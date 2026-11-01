"""The signature on an update: Ed25519 over the download's own bytes, checked before anything inside it is looked at.

Covers the verify-only library (RFC 8032 test vectors, strictness, tampering), the order of the checks in read_release, the
placeholder key (updates stay off), checking and installing from the same bytes, the version rule for a signed older file,
and the offline signing tool. Reads and writes only temporary folders; no network.
Run: python3 dev/run_tests.py test_update_signature
"""
import contextlib
import hashlib
import io
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import ROOT, SRC, TOOLS, VENDOR
import _signing as sg
import ed25519_sign
import ed25519_verify as ev
import sign_release
from clark import update_install as ui, updates
from clark.updates import UpdateError
from test_updates import Base, listed_files, make_zip

# RFC 8032 section 7.1, tests 1 to 3: (private seed, public key, message, signature), all written out in full.
VECTORS = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c", "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025", "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]
SMALL_ORDER = [
    "0100000000000000000000000000000000000000000000000000000000000000",      # the identity
    "ecffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff7f",      # order 2
    "0000000000000000000000000000000000000000000000000000000000000000",      # order 4
    "0000000000000000000000000000000000000000000000000000000000000080",
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac037a",      # order 8
    "c7176a703d4dd84fba3c0b760d10670f2a2053fa2c39ccc64ec7fd7792ac03fa",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc05",
    "26e8958fc2b227b045c3f489f2ef98f0d5dfac05d3c63339b13802886d53fc85",
]


class VerifierTest(unittest.TestCase):
    def test_the_rfc_8032_vectors_verify_and_the_signer_reproduces_them(self):
        for seed, pub, msg, sig in VECTORS:
            seed, pub, msg, sig = (bytes.fromhex(x) for x in (seed, pub, msg, sig))
            self.assertTrue(ev.verify(pub, msg, sig), pub.hex())
            self.assertEqual(pub, ed25519_sign.public_key(seed))
            self.assertEqual(sig, ed25519_sign.sign(seed, msg))

    def test_a_changed_message_key_or_signature_fails(self):
        seed, pub, msg, sig = (bytes.fromhex(x) for x in VECTORS[1])
        self.assertFalse(ev.verify(pub, msg + b"x", sig))
        self.assertFalse(ev.verify(bytes.fromhex(VECTORS[0][1]), msg, sig))          # another key
        for at in (0, 31, 32, 63):
            bad = bytearray(sig)
            bad[at] ^= 1
            self.assertFalse(ev.verify(pub, msg, bytes(bad)), at)

    def test_wrong_lengths_and_the_all_zero_signature_fail(self):
        seed, pub, msg, sig = (bytes.fromhex(x) for x in VECTORS[1])
        for bad in (sig[:63], sig + b"\0", b"", bytes(64)):
            self.assertFalse(ev.verify(pub, msg, bad), len(bad))
        for key in (pub[:31], pub + b"\0", b""):
            self.assertFalse(ev.verify(key, msg, sig), len(key))
        for junk in (None, "text", 5, [1]):
            self.assertFalse(ev.verify(junk, msg, sig))
            self.assertFalse(ev.verify(pub, msg, junk))

    def test_a_second_form_of_the_same_signature_is_refused(self):
        """S + L is the same signature to a lax verifier; here S must be below L."""
        seed, pub, msg, sig = (bytes.fromhex(x) for x in VECTORS[1])
        s = int.from_bytes(sig[32:], "little")
        self.assertLess(s, ev.L)
        twin = sig[:32] + (s + ev.L).to_bytes(32, "little")
        self.assertFalse(ev.verify(pub, msg, twin))
        self.assertFalse(ev.verify(pub, msg, sig[:32] + ev.L.to_bytes(32, "little")))
        self.assertTrue(ev.verify(pub, msg, sig))

    def test_encodings_that_are_not_canonical_are_refused(self):
        seed, pub, msg, sig = (bytes.fromhex(x) for x in VECTORS[1])
        too_big_y = (ev.P + 3).to_bytes(32, "little")                              # y >= p
        self.assertIsNone(ev.decode(too_big_y))
        negative_zero = bytes.fromhex("0100000000000000000000000000000000000000000000000000000000000080")   # x = 0 with the sign bit
        self.assertIsNone(ev.decode(negative_zero))
        self.assertFalse(ev.verify(pub, msg, too_big_y + sig[32:]))                # as R
        self.assertFalse(ev.verify(too_big_y, msg, sig))                           # as the key
        self.assertFalse(ev.verify(negative_zero, msg, sig))

    def test_points_of_small_order_are_refused_as_key_and_as_r(self):
        seed, pub, msg, sig = (bytes.fromhex(x) for x in VECTORS[1])
        for hexed in SMALL_ORDER:
            raw = bytes.fromhex(hexed)
            point = ev.decode(raw)
            self.assertIsNotNone(point, hexed)
            self.assertTrue(ev.small_order(point), hexed)
            self.assertFalse(ev.verify(raw, msg, sig), hexed)                      # as the key
            self.assertFalse(ev.verify(raw, msg, raw + bytes(32)), hexed)          # the classic forgery shape
            self.assertFalse(ev.verify(pub, msg, raw + sig[32:]), hexed)           # as R
        self.assertFalse(ev.small_order(ev.decode(pub)))


class SignedBase(Base):
    def setUp(self):
        super().setUp()

    def with_sig(self, path, data=None):
        sig = Path(str(path) + ".sig")
        if data is None:
            sig.unlink(missing_ok=True)
        else:
            sig.write_bytes(data)
        return sig


class SignatureCheckTest(SignedBase):
    def test_a_signed_update_reads(self):
        self.assertEqual("0.3.1", self.read(make_zip(self.tmp)).version)

    def test_the_signed_message_is_the_domain_and_the_bytes(self):
        self.assertEqual(b"clark-release-v1\0", updates.SIGN_DOMAIN)
        path = make_zip(self.tmp, sign=False)
        data = path.read_bytes()
        self.with_sig(path, ed25519_sign.sign(sg.TEST_SEED, data))                  # signed without the domain
        self.refuses(path, "badsig")
        self.with_sig(path, ed25519_sign.sign(sg.TEST_SEED, b"clark-release-v2\0" + data))
        self.refuses(path, "badsig")
        self.with_sig(path, ed25519_sign.sign(sg.TEST_SEED, updates.SIGN_DOMAIN + data))
        self.assertEqual("0.3.1", self.read(path).version)

    def test_no_signature_file_is_refused_in_plain_words(self):
        path = make_zip(self.tmp, sign=False)
        err = self.refuses(path, "unsigned", detail="no .sig file")
        self.assertIn("no signature", err.message)
        self.assertNotRegex(err.message, r"(?i)\b(zip|manifest|sha)\b")

    def test_a_signature_of_the_wrong_length_is_refused(self):
        path = make_zip(self.tmp)
        good = Path(str(path) + ".sig").read_bytes()
        for bad in (b"", good[:63], good + b"\0", good * 2):
            self.with_sig(path, bad)
            self.refuses(path, "badsig", detail="the signature file is")

    def test_a_wrong_signature_or_a_wrong_key_is_refused(self):
        path = make_zip(self.tmp)
        sig = bytearray(Path(str(path) + ".sig").read_bytes())
        sig[10] ^= 4
        self.with_sig(path, bytes(sig))
        self.refuses(path, "badsig", detail="the signature does not verify")
        self.with_sig(path, sg.signature_for(path.read_bytes(), sg.OTHER_SEED))      # properly made, by another key
        self.refuses(path, "badsig", detail="the signature does not verify")
        mock.patch.object(updates, "RELEASE_PUBLIC_KEY", sg.OTHER_PUBLIC).start()
        self.addCleanup(mock.patch.stopall)                                 # or the app trusts another key
        self.with_sig(path, sg.signature_for(path.read_bytes()))
        self.refuses(path, "badsig")

    def test_a_forged_update_with_a_rewritten_manifest_is_refused(self):
        """The case the signature exists for: a different file whose manifest agrees with its contents."""
        real = make_zip(self.tmp)
        forged = make_zip(self.fresh(), files={**listed_files(), "src/clark/store.py": b"import os  # evil\n"}, sign=False)
        with mock.patch.object(updates, "check_signature"):                         # without the signature it passes every other check
            self.assertEqual("0.3.1", self.read(forged).version)
        shutil.copyfile(str(real) + ".sig", str(forged) + ".sig")                  # the real signature on the forged bytes
        self.refuses(forged, "badsig")
        self.with_sig(forged, sg.signature_for(forged.read_bytes(), sg.OTHER_SEED))
        self.refuses(forged, "badsig")

    def test_a_file_changed_after_signing_is_refused(self):
        path = make_zip(self.tmp)
        with open(path, "ab") as f:
            f.write(b"\0")
        self.refuses(path, "badsig")

    def test_the_signature_is_checked_before_the_zip_is_opened(self):
        junk = Path(self.tmp) / "clark-0.3.1-mac.zip"
        junk.write_bytes(b"not a zip at all")
        self.refuses(junk, "unsigned")                                              # not "damaged"
        self.with_sig(junk, sg.signature_for(junk.read_bytes()))
        self.refuses(junk, "damaged")                                               # signed junk gets past the signature only
        wrong = make_zip(self.fresh(), system="linux", name="clark-0.3.1-mac.zip", sign=False)
        self.refuses(wrong, "unsigned")                                             # the system rule comes after

    def test_a_link_in_place_of_the_signature_is_refused(self):
        path = make_zip(self.tmp)
        sig = Path(str(path) + ".sig")
        other = Path(self.fresh()) / "real.sig"
        shutil.move(str(sig), other)
        os.symlink(other, sig)
        self.refuses(path, "badsig")

    def test_the_placeholder_key_refuses_everything_unless_a_key_is_passed(self):
        path = make_zip(self.tmp)
        mock.patch.object(updates, "RELEASE_PUBLIC_KEY", updates.PLACEHOLDER_KEY).start()
        self.addCleanup(mock.patch.stopall)
        self.assertEqual(32, len(updates.PLACEHOLDER_KEY))
        self.refuses(path, "nokey", detail="RELEASE_PUBLIC_KEY is still the placeholder")
        self.assertEqual("0.3.1", updates.read_release(path, "mac", "0.3.0", 2, public_key=sg.TEST_PUBLIC).version)
        self.refuses(make_zip(self.fresh(), sign=False), "nokey")                   # unsigned too: off is off

    def test_the_shipped_key_is_still_the_placeholder_until_the_release_key_exists(self):
        source = (SRC / "clark" / "updates.py").read_text(encoding="utf-8")
        self.assertIn("REPLACE WITH THE RELEASE KEY BEFORE THE FIRST SIGNED RELEASE", source)
        self.assertIn("RELEASE_PUBLIC_KEY = PLACEHOLDER_KEY", source)


class VersionRuleTest(SignedBase):
    def test_a_signed_older_update_is_refused_even_when_installing_again_is_asked(self):
        old = make_zip(self.tmp, version="0.2.0")
        self.refuses(old, "older", installed="0.3.0")
        self.refuses(old, "older", installed="0.3.0", reinstall=True)
        self.assertIn("by hand", updates.MESSAGES["older"])

    def test_the_same_version_needs_install_again_and_a_newer_one_does_not(self):
        same = make_zip(self.tmp, version="0.3.0")
        self.refuses(same, "same", installed="0.3.0")
        self.assertEqual("0.3.0", self.read(same, installed="0.3.0", reinstall=True).version)
        self.assertEqual("0.4.0", self.read(make_zip(self.fresh(), version="0.4.0")).version)

    def test_the_version_in_the_name_must_be_the_one_in_the_files(self):
        path = make_zip(self.tmp, version="0.3.2", name="clark-0.3.1-mac.zip")      # signed, but the name says another version
        self.refuses(path, "damaged")


class ParsedVersionTest(SignedBase):
    """Versions are compared as numbers (X, Y, Z), never as text, and only a plain X.Y.Z is accepted."""

    def test_ordering_is_numeric(self):
        self.assertEqual("0.3.10", self.read(make_zip(self.tmp, version="0.3.10"), installed="0.3.9").version)   # as text 10 < 9
        self.refuses(make_zip(self.fresh(), version="0.3.9"), "older", installed="0.3.10")
        self.assertEqual("0.10.0", self.read(make_zip(self.fresh(), version="0.10.0"), installed="0.9.9").version)
        self.refuses(make_zip(self.fresh(), version="0.4.0"), "same", installed="0.4.0")

    def test_a_version_that_is_not_plain_x_y_z_never_parses(self):
        for bad in ("0.4", "0.4.0.0", "01.2.3", "0.03.1", "0.4.0+local", "0.4.0-rc1", "0.4.0rc1", "v0.4.0", " 0.4.0", "0.4.0 ", "0.4.0\n",
                    "\u0664.0.0", "", "0.4.0.dev1x"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                updates.version_key(bad)

    def test_a_manifest_version_that_is_not_plain_is_refused_even_if_signed(self):
        for text in ("0.4", "0.4.0+local", "0.4.0-rc1", "00.4.0", "0.4.00"):
            with self.subTest(text=text):
                path = make_zip(self.fresh(), version="0.4.0", manifest=lambda doc, t=text: doc.update(version=t))
                self.refuses(path, "damaged")

    def test_a_manifest_version_that_differs_from_the_file_name_is_refused_for_the_same_version_too(self):
        """Built so that only the name check can refuse it: the top folder, the manifest and the version inside the files all
        agree with each other, are plain X.Y.Z, and are signed; only the file name says another version."""
        for named, inside in (("0.4.1", "0.4.0"), ("0.4.0", "0.4.1"), ("0.3.0", "0.3.1"), ("0.3.1", "0.3.0")):
            with self.subTest(named=named, inside=inside):
                path = make_zip(self.fresh(), version=inside, name=f"clark-{named}-mac.zip")
                err = self.refuses(path, "damaged", installed="0.3.0", reinstall=True)
                self.assertIn(f"manifest {inside}, name {named}", err.detail)

    def test_two_differently_built_files_of_one_version_signed_by_the_one_key_are_both_accepted(self):
        """Accepted on purpose, no action: the key holder decides what counts as the release; the signature does not pick one build."""
        first = make_zip(self.fresh(), notes="Build one.\n")
        second = make_zip(self.fresh(), notes="Build two.\n", files={**listed_files(), "README.md": b"A different build.\n"})
        self.assertNotEqual(first.read_bytes(), second.read_bytes())
        self.assertEqual("Build one.\n", self.read(first).notes)
        self.assertEqual("Build two.\n", self.read(second).notes)


class OneSetOfBytesTest(SignedBase):
    def test_a_file_replaced_after_the_check_does_not_change_what_is_staged(self):
        path = make_zip(self.tmp)
        release = self.read(path)
        evil = make_zip(self.fresh(), files={**listed_files(), "src/clark/x.py": b"evil\n"})
        os.replace(evil, path)                                                      # swapped on disk after the check
        app = Path(self.fresh())
        staging = ui.stage(release, app, "20261101T000000Z")
        self.assertNotEqual(b"evil\n", (staging / "src" / "clark" / "x.py").read_bytes())
        self.assertEqual(release.files["src/clark/x.py"]["sha256"],
                         hashlib.sha256((staging / "src" / "clark" / "x.py").read_bytes()).hexdigest())

    def test_staging_never_falls_back_to_the_file_on_disk(self):
        release = self.read(make_zip(self.tmp))
        release.data = b""
        with self.assertRaises(ui.InstallError):
            ui.stage(release, Path(self.fresh()), "20261101T000000Z")

    def test_take_in_keeps_the_signature_with_the_private_copy_and_it_is_checked_there(self):
        path = make_zip(self.tmp)
        data_dir = self.fresh()
        kept, digest = ui.take_in(path, data_dir, "mac")
        self.assertEqual(Path(str(path) + ".sig").read_bytes(), Path(str(kept) + ".sig").read_bytes())
        self.assertEqual("0.3.1", ui.read_taken(kept, digest, "mac", "0.3.0", 2).version)
        os.unlink(path)                                                              # the original can go: nothing needs it
        os.unlink(str(path) + ".sig")
        self.assertEqual("0.3.1", ui.read_taken(kept, digest, "mac", "0.3.0", 2).version)

    def test_a_kept_copy_changed_after_review_is_refused(self):
        path = make_zip(self.tmp)
        kept, digest = ui.take_in(path, self.fresh(), "mac")
        forged = make_zip(self.fresh(), files={**listed_files(), "src/clark/x.py": b"evil\n"}, sign=False)
        shutil.copyfile(forged, kept)                                                # bytes swapped, old signature left
        with self.assertRaises(UpdateError) as said:
            ui.read_taken(kept, digest, "mac", "0.3.0", 2)
        self.assertEqual("badsig", said.exception.key)

    def test_the_folder_take_in_keeps_its_copy_in_is_private(self):
        data_dir = self.fresh()
        kept, _ = ui.take_in(make_zip(self.tmp), data_dir, "mac")
        if os.name != "nt":
            self.assertEqual(0o700, stat.S_IMODE(os.stat(kept.parent).st_mode))
            self.assertEqual(0o600, stat.S_IMODE(os.stat(kept).st_mode))
            self.assertEqual(0o600, stat.S_IMODE(os.stat(str(kept) + ".sig").st_mode))

    def test_take_in_does_not_leave_an_old_signature_beside_an_unsigned_file(self):
        data_dir = self.fresh()
        ui.take_in(make_zip(self.tmp), data_dir, "mac")
        unsigned = make_zip(self.fresh(), sign=False)
        kept, digest = ui.take_in(unsigned, data_dir, "mac")
        self.assertFalse(Path(str(kept) + ".sig").exists())
        with self.assertRaises(UpdateError) as said:
            ui.read_taken(kept, digest, "mac", "0.3.0", 2)
        self.assertEqual("unsigned", said.exception.key)


class ShippedKeyTest(unittest.TestCase):
    def test_the_pinned_key_is_the_placeholder_or_a_real_key_that_is_not_a_test_key(self):
        # No test trusts a key at import any more (trust_test_key patches one test at a time), so this reads the shipped constant.
        key = updates.RELEASE_PUBLIC_KEY
        self.assertIsInstance(key, bytes)
        self.assertEqual(32, len(key))
        if key == updates.PLACEHOLDER_KEY:
            return
        # AFTER `sign_release.py keygen` (the owner, offline): add here a pin of hashlib.sha256(key).hexdigest() to the digest
        # published in that release's notes, so a swapped key fails this test. Until then, the shape rules below are all we can hold.
        self.assertNotIn(key, (sg.TEST_PUBLIC, sg.OTHER_PUBLIC) + tuple(bytes.fromhex(v[1]) for v in VECTORS))
        self.assertIsNotNone(ev.decode(key), "the pinned key is not a point on the curve")
        self.assertFalse(ev.small_order(ev.decode(key)))

    def test_the_test_key_is_not_trusted_unless_a_test_asks_for_it(self):
        self.assertNotEqual(sg.TEST_PUBLIC, updates.RELEASE_PUBLIC_KEY)


class SeparationTest(unittest.TestCase):
    def test_nothing_in_the_app_can_import_the_signer(self):
        for folder in (SRC, VENDOR):
            for path in folder.rglob("*.py"):
                text = path.read_text(encoding="utf-8")
                self.assertNotRegex(text, r"(?m)^\s*(import|from)\s+(ed25519_sign|sign_release)\b", path)
            self.assertFalse(list(folder.rglob("ed25519_sign*")))
        self.assertFalse(hasattr(ev, "sign"))
        self.assertTrue((TOOLS / "ed25519_sign.py").is_file())

    def test_the_signer_and_the_verifier_share_one_domain_constant(self):
        self.assertIs(sign_release.updates.SIGN_DOMAIN, updates.SIGN_DOMAIN)


class FakeKeychain:
    """An in-memory stand-in for `security`: the tests' only way to reach the Keychain. Records every argv and every stdin."""

    def __init__(self):
        self.items, self.argvs, self.stdins = {}, [], []

    def __call__(self, args, stdin=None):
        args = list(args)
        self.argvs.append(args)
        self.stdins.append(stdin)
        if args == ["-i"]:
            words = stdin.split()
            assert words[0] == "add-generic-password", stdin
            key = (words[words.index("-s") + 1], words[words.index("-a") + 1])
            if key in self.items:
                return 45, ""
            self.items[key] = words[words.index("-w") + 1]
            return 0, ""
        assert args[0] == "find-generic-password", args
        key = (args[args.index("-s") + 1], args[args.index("-a") + 1])
        if key not in self.items:
            return 44, ""
        return 0, (self.items[key] + "\n") if "-w" in args else ""


class SigningToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark sign "))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.keychain = FakeKeychain()

        def refuse(*a, **k):
            raise AssertionError("the real Keychain was reached")
        patcher = mock.patch.object(sign_release, "run_security", self.keychain)
        patcher.start()
        self.addCleanup(patcher.stop)
        for name in ("subprocess.run", "subprocess.Popen"):                          # and nothing else may start a program
            p = mock.patch(name, side_effect=refuse)
            p.start()
            self.addCleanup(p.stop)

    def run_main(self, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = sign_release.main(list(argv))
        return code, out.getvalue()

    def stored_seed(self, name="release"):
        return bytes.fromhex(self.keychain.items[(sign_release.SERVICE, name)])

    def test_keygen_stores_the_seed_in_the_keychain_and_prints_only_the_public_key(self):
        code, out = self.run_main("keygen")
        seed = self.stored_seed()
        self.assertEqual((0, 32), (code, len(seed)))
        self.assertEqual("public key: " + ed25519_sign.public_key(seed).hex() + "\n", out)
        self.assertNotIn(seed.hex(), out)
        code, out = self.run_main("keygen")                                         # never over an existing key
        self.assertEqual(1, code)
        self.assertEqual(seed, self.stored_seed())
        self.assertNotIn(seed.hex(), out)

    def test_the_seed_is_never_in_an_argument_list_only_on_standard_input(self):
        self.run_main("keygen", "other")
        seed_hex = self.stored_seed("other").hex()
        for argv in self.keychain.argvs:
            for word in argv:
                self.assertNotIn(seed_hex[:16], word)
        self.assertIn(seed_hex, "".join(s for s in self.keychain.stdins if s))
        self.assertEqual(["-i"], [a for a in self.keychain.argvs if "-i" in a][0])
        self.run_main("public", "other")
        self.assertIn("-w", self.keychain.argvs[-1])                                # read back with find-generic-password -w

    def test_no_code_path_writes_the_seed_to_disk(self):
        written = []
        real_open, real_os_open = open, os.open

        def spy_open(file, mode="r", *a, **k):
            if isinstance(file, (str, bytes, os.PathLike)) and any(c in mode for c in "wax+"):
                written.append(("open", str(file)))
            return real_open(file, mode, *a, **k)

        def spy_os_open(path, flags, *a, **k):
            if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
                written.append(("os.open", str(path)))
            return real_os_open(path, flags, *a, **k)
        zip_path = self.tmp / "clark-0.3.1-mac.zip"
        zip_path.write_bytes(b"release bytes")
        with mock.patch("builtins.open", spy_open), mock.patch("os.open", spy_os_open):
            self.run_main("keygen")
            seed = self.stored_seed()
            self.run_main("public")
            self.run_main("sign", str(zip_path))
        for kind, path in written:                                                  # only the signature file may be written
            self.assertTrue(path.endswith(".sig"), (kind, path))
        for path in self.tmp.rglob("*"):
            if path.is_file():
                self.assertNotIn(seed, path.read_bytes())
                self.assertNotIn(seed.hex().encode(), path.read_bytes())
        source = (TOOLS / "sign_release.py").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"scrypt|getpass|O_CREAT|os\.open|0o600|write_bytes\(seed|\.write\(seed")
        self.assertEqual(1, len(re.findall(r"subprocess\.run\(", source)))             # one place runs `security`

    def test_sign_writes_a_signature_the_app_accepts_and_prints_no_key(self):
        self.keychain.items[(sign_release.SERVICE, "release")] = sg.TEST_SEED.hex()
        zip_path = self.tmp / "clark-0.3.1-mac.zip"
        zip_path.write_bytes(b"some release bytes")
        code, out = self.run_main("sign", str(zip_path))
        self.assertEqual(0, code)
        self.assertNotIn(sg.TEST_SEED.hex(), out)
        sig = Path(str(zip_path) + ".sig").read_bytes()
        self.assertTrue(ev.verify(sg.TEST_PUBLIC, updates.SIGN_DOMAIN + b"some release bytes", sig))

    def test_a_missing_or_damaged_key_is_refused_and_no_signature_is_written(self):
        zip_path = self.tmp / "clark-0.3.1-mac.zip"
        zip_path.write_bytes(b"x")
        code, out = self.run_main("sign", str(zip_path))
        self.assertEqual(1, code)
        self.keychain.items[(sign_release.SERVICE, "release")] = "not hex"
        code, out = self.run_main("sign", str(zip_path))
        self.assertEqual(1, code)
        code, out = self.run_main("keygen", "bad name!")
        self.assertEqual(1, code)
        self.assertFalse(Path(str(zip_path) + ".sig").exists())

    def test_the_fake_keychain_is_the_only_way_in(self):
        self.assertIsInstance(sign_release.run_security, FakeKeychain)
        with self.assertRaises(AssertionError):
            subprocess.run(["true"])

    def test_a_bad_command_line_prints_the_help_and_the_runbook(self):
        code, out = self.run_main("nonsense")
        self.assertEqual(2, code)
        self.assertIn("Key loss or compromise", out)


class SigningProgramTest(unittest.TestCase):
    def test_run_as_a_program_it_refuses_an_unknown_command(self):
        done = subprocess.run([sys.executable, str(TOOLS / "sign_release.py")], capture_output=True, text=True)
        self.assertEqual(2, done.returncode)


if __name__ == "__main__":
    unittest.main()
