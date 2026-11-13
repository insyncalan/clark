# pypdf, bundled for clark (#891)

- Library: pypdf 6.21.4 (pure Python), licence BSD-3-Clause (the text is in `LICENSE`, beside this file).
- Source: https://pypi.org/project/pypdf/6.21.4/ , the wheel `pypdf-6.21.4-py3-none-any.whl`.
- SHA-256 of that wheel: `33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c`
- Copied unchanged: every file here except this one is byte for byte the wheel's `pypdf/` folder and its `LICENSE` (from
  the wheel's `dist-info/licenses/`). `vendor/manifest.json` holds the SHA-256 of each file.
- Its one dependency on Python 3.9 and 3.10 is `typing_extensions` 4.16.0, bundled as the single file `vendor/typing_extensions.py`
  (wheel `typing_extensions-4.16.0-py3-none-any.whl`, SHA-256 `481caa481374e813c1b176ada14e97f1f67a4539ce9cfeb3f350d78d6370c2e8`).
  The optional extras (cryptography, Pillow and the rest) are not bundled: an encrypted PDF is skipped, never decrypted.
- clark imports it only inside a separate reader process, never in the server process.
- Upgrade only deliberately: replace this folder with the new wheel's, change LIBRARIES in `dev/tools/vendor_manifest.py`, run it,
  run the tests, and commit the library and the manifest together.
