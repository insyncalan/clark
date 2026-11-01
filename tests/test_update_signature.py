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
        sg.use_test_key()
        self.addCleanup(sg.use_test_key)

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
        updates.RELEASE_PUBLIC_KEY = sg.OTHER_PUBLIC                                # or the app trusts another key
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
        updates.RELEASE_PUBLIC_KEY = updates.PLACEHOLDER_KEY
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
        for named, inside in (("0.3.0", "0.3.1"), ("0.3.0", "0.3.00"), ("0.3.0", "0.3"), ("0.3.1", "0.3.0")):
            with self.subTest(named=named, inside=inside):
                path = make_zip(self.fresh(), version=named, manifest=lambda doc, v=inside: doc.update(version=v))
                self.refuses(path, "damaged", installed="0.3.0", reinstall=True)

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


class SigningToolTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="clark sign "))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def run_main(self, *argv, ask=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = sign_release.main(list(argv), ask=ask or (lambda prompt: "pw"))
        return code, out.getvalue()

    def test_keygen_prints_only_the_public_key_and_makes_a_private_file(self):
        key = self.tmp / "release.key"
        code, out = self.run_main("keygen", str(key))
        seed = key.read_bytes()
        self.assertEqual((0, 32), (code, len(seed)))
        self.assertEqual(0o600, stat.S_IMODE(os.stat(key).st_mode))
        self.assertEqual("public key: " + ed25519_sign.public_key(seed).hex() + "\n", out)
        self.assertNotIn(seed.hex(), out)
        code, _ = self.run_main("keygen", str(key))                                 # never over an existing key
        self.assertEqual(1, code)
        self.assertEqual(seed, key.read_bytes())

    def test_sign_writes_a_signature_the_app_accepts_and_prints_no_key(self):
        key, zip_path = self.tmp / "k", self.tmp / "clark-0.3.1-mac.zip"
        key.write_bytes(sg.TEST_SEED)
        os.chmod(key, 0o600)
        zip_path.write_bytes(b"some release bytes")
        code, out = self.run_main("sign", str(key), str(zip_path))
        self.assertEqual(0, code)
        self.assertNotIn(sg.TEST_SEED.hex(), out)
        sig = Path(str(zip_path) + ".sig").read_bytes()
        self.assertTrue(ev.verify(sg.TEST_PUBLIC, updates.SIGN_DOMAIN + b"some release bytes", sig))

    def test_a_key_that_others_can_read_or_that_is_inside_the_repo_is_refused(self):
        key = self.tmp / "k"
        key.write_bytes(sg.TEST_SEED)
        os.chmod(key, 0o644)
        zip_path = self.tmp / "clark-0.3.1-mac.zip"
        zip_path.write_bytes(b"x")
        code, out = self.run_main("sign", str(key), str(zip_path))
        self.assertEqual(1, code)
        self.assertIn("chmod 600", out)
        self.assertFalse(Path(str(zip_path) + ".sig").exists())
        inside = Path(tempfile.mkdtemp(dir=ROOT / "dev"))                           # a folder in the repo
        self.addCleanup(shutil.rmtree, inside, True)
        for command in (("keygen", str(inside / "k")), ("sign", str(inside / "k"), str(zip_path))):
            code, out = self.run_main(*command)
            self.assertEqual(1, code)
            self.assertIn("inside the clark repository", out)
        self.assertFalse((inside / "k").exists())
        link = self.tmp / "link"                                                    # a link that leads into the repo
        os.symlink(inside, link)
        code, out = self.run_main("keygen", str(link / "k"))
        self.assertEqual(1, code)
        self.assertFalse((inside / "k").exists())

    @unittest.skipUnless(hasattr(hashlib, "scrypt"), "this Python has no scrypt")
    def test_a_passphrase_protected_key_round_trips_and_a_wrong_passphrase_is_refused(self):
        key = self.tmp / "p.key"
        code, out = self.run_main("keygen", str(key), "--passphrase", ask=lambda prompt: "correct horse")
        self.assertEqual(0, code)
        blob = key.read_bytes()
        self.assertTrue(blob.startswith(sign_release.MAGIC))
        code, shown = self.run_main("public", str(key), ask=lambda prompt: "correct horse")
        self.assertEqual((0, out), (code, shown))
        code, shown = self.run_main("public", str(key), ask=lambda prompt: "wrong")
        self.assertEqual(1, code)
        self.assertIn("wrong passphrase", shown)

    def test_a_bad_command_line_prints_the_help_and_the_runbook(self):
        code, out = self.run_main("nonsense")
        self.assertEqual(2, code)
        self.assertIn("Key loss or compromise", out)

    def test_run_as_a_program_it_refuses_an_unknown_command(self):
        done = subprocess.run([sys.executable, str(TOOLS / "sign_release.py")], capture_output=True, text=True)
        self.assertEqual(2, done.returncode)


if __name__ == "__main__":
    unittest.main()
