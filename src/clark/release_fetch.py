"""Settings › Version and updates: looking for the newest release on the project's public releases page and downloading it.

The one place clark makes an outbound call of its own (an exception the owner allowed). What it sends is only a request for a public
page: no token, no cookie, no sign-in, nothing about the person, the computer or the installed version, and one fixed generic
User-Agent. It never installs anything: it hands back the newest release's facts, or the bytes of its file for this computer, and
updater.py runs the same review and checks on them as on a file from Downloads.

  latest(system, opener)     the newest release: {"version", "date", "size", "notes", "url", "digest", "sig_url"}, or raises FetchError
  download(url, dest, ...)   stream the file into `dest` (at most updates.MAX_ZIP_BYTES), report progress, stop on cancel

Only https, only the hosts in HOSTS, and a redirect only to a host in HOSTS: anything else is refused before a byte is read.
`opener(request, timeout)` is the seam for the tests (it answers a file-like object with .read, .headers and .geturl).
A refusal's detail is for the log; its key picks the sentence in updater.py. No sentence here holds a path or an address.
"""
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from clark import updates

API_URL = "https://api.github.com/repos/insyncalan/clark/releases/latest"
HOSTS = ("api.github.com", "github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com")
USER_AGENT = "clark"
ACCEPT = "application/vnd.github+json"
TIMEOUT = 15
MAX_API_BYTES = 1024 * 1024
MAX_REDIRECTS = 5
NO_NOTES = "There are no notes for this version."
DIGEST_RE = re.compile(r"^sha256:([0-9a-f]{64})$")


class FetchError(Exception):
    """`key` picks the sentence: "offline" (could not reach it, or the connection stopped: the only one that says offline),
    "nofile" (the release has no file for this computer), "unreadable" (the releases page answered something clark cannot use),
    "refused" (a host or a scheme not allowed), "toobig", "cancelled", "damaged" (the download is short), "mismatch" (the bytes
    do not match the digest the page gave), "save" (the file could not be written here)."""

    def __init__(self, key, detail=""):
        self.key = key
        self.detail = detail
        super().__init__(key)


def allowed(url):
    """True only for an https address on one of HOSTS, with no user name or other sign-in part and no odd port."""
    try:
        parts = urllib.parse.urlsplit(url)
        return (parts.scheme == "https" and parts.hostname in HOSTS and parts.username is None and parts.password is None
                and parts.port in (None, 443))
    except ValueError:
        return False


class _Redirects(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_REDIRECTS

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise FetchError("refused", "a redirect to an address that is not allowed")
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            for name in list(new.headers):
                if name.lower() not in ("user-agent", "accept"):
                    del new.headers[name]
        return new


def real_opener(request, timeout):
    """The real network call: no proxy settings from the environment are needed for a public page, but the system's are honoured
    (urllib's default); no cookies are kept; redirects are checked by `_Redirects`."""
    send = urllib.request.build_opener(_Redirects).open       # a network request, not a file: it takes no text mode, so the encoding rule of test_platform_source does not apply
    return send(request, timeout=timeout)


default_opener = real_opener    # what the updater uses when it is given none; the tests' shared helper (tests/_paths.py) swaps it for one that cannot reach the network


def _request(url):
    if not allowed(url):
        raise FetchError("refused", "an address that is not allowed")
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": ACCEPT}, method="GET")


def _open(url, opener, timeout):
    try:
        response = opener(_request(url), timeout)
    except FetchError:
        raise
    except urllib.error.HTTPError as e:                              # the page answered, with an error status: not "offline"
        raise FetchError("unreadable", f"the page answered with status {e.code}")
    except (OSError, urllib.error.URLError, ValueError) as e:       # a refused connection, a timeout, a TLS or proxy failure
        raise FetchError("offline", f"the call failed: {type(e).__name__}")
    final = getattr(response, "geturl", lambda: url)()
    if not allowed(final):
        response.close()
        raise FetchError("refused", "the answer came from an address that is not allowed")
    return response


def newer(found_version, installed_version):
    """True when `found_version` is a later release than `installed_version` (an equal or older one is not an update)."""
    try:
        return updates.version_key(found_version) > updates.version_key(installed_version)
    except ValueError:
        return False


def _notes(body):
    """The release notes as updates shows them: its clean_notes (so its MAX_NOTES and no hidden marks), or this file's NO_NOTES when blank."""
    cleaned = updates.clean_notes(body) if isinstance(body, str) else ""
    return cleaned if cleaned.strip() else NO_NOTES


def latest(system, opener=real_opener, timeout=TIMEOUT):
    """The newest release with a file for `system`: {"version", "date" (YYYY-MM-DD or ""), "size", "notes", "url", "digest" (hex or None),
    "sig_url" (the address of the signature file beside it, or None when the release has none)}.
    FetchError "offline" when it could not be reached, "unreadable" when the answer cannot be used, "nofile" for a release with no file
    for this computer, "toobig" for a file over the cap."""
    response = _open(API_URL, opener, timeout)
    try:
        raw = response.read(MAX_API_BYTES + 1)
    except OSError as e:
        raise FetchError("offline", f"reading the answer failed: {type(e).__name__}")
    finally:
        response.close()
    if len(raw) > MAX_API_BYTES:
        raise FetchError("unreadable", "the answer is too long")
    try:
        doc = json.loads(raw.decode("utf-8"), parse_int=_small_int)
    except (ValueError, UnicodeDecodeError):
        raise FetchError("unreadable", "the answer is not JSON")
    if not isinstance(doc, dict) or doc.get("draft") is True or doc.get("prerelease") is True:
        raise FetchError("unreadable", "the answer is not a release")
    tag = doc.get("tag_name")
    version = tag[1:] if isinstance(tag, str) and tag[:1] == "v" else tag
    if not isinstance(version, str) or not updates.is_release_version(version):
        raise FetchError("unreadable", "the release has no usable version")
    name = f"clark-{version}-{system}.zip"
    for asset in doc.get("assets") if isinstance(doc.get("assets"), list) else []:
        if not isinstance(asset, dict) or asset.get("name") != name:
            continue
        url, size = asset.get("browser_download_url"), asset.get("size")
        if not isinstance(url, str) or not allowed(url) or not isinstance(size, int) or isinstance(size, bool) or size <= 0:
            raise FetchError("unreadable", "the file's facts are not usable")
        if size > updates.MAX_ZIP_BYTES:
            raise FetchError("toobig", "the file is over the cap")
        found = DIGEST_RE.match(asset.get("digest")) if isinstance(asset.get("digest"), str) else None
        published = doc.get("published_at")
        date = published[:10] if isinstance(published, str) and re.match(r"^\d{4}-\d{2}-\d{2}", published) else ""
        return {"version": version, "date": date, "size": size, "notes": _notes(doc.get("body")), "url": url,
                "digest": found.group(1) if found else None, "sig_url": _sig_url(doc["assets"], name + updates.SIGNATURE_SUFFIX)}
    raise FetchError("nofile", "the release has no file for this computer")


def _sig_url(assets, name):
    """The address of the release's signature file for the download, when the release has one on an allowed address, else None.
    It is fetched by updater.py only for a release that must carry one (updates.signature_required: from 1.3.4 up)."""
    for asset in assets:
        if isinstance(asset, dict) and asset.get("name") == name:
            url = asset.get("browser_download_url")
            return url if isinstance(url, str) and allowed(url) else None
    return None


def _small_int(text):
    if len(text.lstrip("-")) > 12:
        raise ValueError("number too long")
    return int(text)


def download(url, dest, progress=None, cancelled=None, expected_size=None, digest=None, opener=real_opener, timeout=TIMEOUT,
             max_bytes=None):
    """Stream `url` into the new file `dest` (never replacing one that is not whole), at most `max_bytes` (default MAX_ZIP_BYTES). `progress(done, total)` is
    called after each chunk (total None when unknown); `cancelled()` is asked before each chunk and, when true, removes the partial
    file and raises "cancelled". The file's SHA-256 must equal `digest` when one is given and its length `expected_size` when that is
    given, else "damaged". Returns the SHA-256 (hex). A partial file is never left behind."""
    response = _open(url, opener, timeout)
    dest = Path(dest)
    part = dest.with_name(dest.name + ".part")
    h, got = hashlib.sha256(), 0
    cap = updates.MAX_ZIP_BYTES if max_bytes is None else max_bytes
    try:
        try:
            total = int(response.headers.get("Content-Length") or 0) or expected_size
        except (ValueError, TypeError, AttributeError):
            total = expected_size
        if total and total > cap:
            raise FetchError("toobig", "the file is over the cap")
        with open(part, "wb") as out:
            while True:
                if cancelled is not None and cancelled():
                    raise FetchError("cancelled", "stopped by the person")
                try:
                    chunk = response.read(updates.CHUNK)
                except OSError as e:
                    raise FetchError("offline", f"the download stopped: {type(e).__name__}")
                if not chunk:
                    break
                got += len(chunk)
                if got > cap:
                    raise FetchError("toobig", "the download grew past the cap")
                h.update(chunk)
                out.write(chunk)
                if progress is not None:
                    progress(got, total)
            out.flush()
        if expected_size is not None and got != expected_size:
            raise FetchError("damaged", f"the download is {got} bytes, not {expected_size}")
        if digest is not None and h.hexdigest() != digest:
            raise FetchError("mismatch", "the download does not match the digest the page gave")
        part.replace(dest)
    except OSError as e:
        raise FetchError("save", f"the download could not be saved: {type(e).__name__}")
    finally:
        response.close()
        part.unlink(missing_ok=True)
    return h.hexdigest()
