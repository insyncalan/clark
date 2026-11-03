"""AI providers for ask clark (#54): where a key lives, the one way clark reaches a provider over the network, the fakes, and which
provider answers a question. GUARDED: it touches secrets and makes clark's first outgoing calls. Two readers, and the owner approves
the exact code.

SOURCE (#53, "copy from the branch", the owner, 01-11-2026): creaite branch v27-132-build at a6249e2df4332fb17a28419c40db24ed47fd79cb,
system/scripts/providers.py. Copied CHANGED, per the #53 review's section 6: the KeyStore seam (has, put, remove, peek), the model
list (HttpsLister: host table, https only, no proxy, no redirect, TLS 1.2 or later, the key in one header, a cap on bytes read), the
OpenAI direct call (DirectCaller, `store: false`), FakeLister and the fake-mode gate. LIMIT_TEXT went to ask_claude.py (it reads the command's result). Every difference is marked
`clark:`. NOT copied: the four kinds of job, the confidential-material gate, the other three providers, the settings catalogue, the
debug log, the pending-key holder (clark tests and keeps the key in one request). The Anthropic Messages call is NEW code: creaite has
no Claude key call (its G8 is unbuilt).

THE KEY. It lives in the Mac's keychain only (platform.keychain_*), as service `clark.ai.<data folder id>.<provider>`, account `clark`.
`has` never reads it; `peek` reads it for one provider call and the caller drops it. No route, reply, log line, error, file or setting
ever holds it. Errors here carry a provider name and an HTTP status, never a key, a request or a reply body.

EVERY OUTGOING CALL (Https): an exact host from HOSTS (api.anthropic.com, api.openai.com) and an exact path; https only; TLS 1.2 or
later, verified against the system's certificates; no redirect followed (a 3xx is "couldn't reach", and the key is never sent twice);
no proxy taken from the environment; a total time limit (clark: not only per read), a cap on bytes sent, on bytes read and on reply
tokens; the key in one header only (x-api-key, or Authorization: Bearer), never the address or the body. No tools are ever asked for.
No module but this one imports urllib.request or ssl (tests/test_ai_providers.py).

FAKES: CLARK_FAKE_PROVIDERS=1 is honoured only when the data folder is inside the system's temporary folder or the repository has a
`.clark-dev` marker; anywhere else it is ignored. Under it, keys live in memory and no network is touched.
"""
import hashlib
import json
import os
import re
import ssl
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from clark import ask, platform

PROVIDERS = ("claude", "openai")
NAMES = {"claude": "Claude", "openai": "OpenAI"}
HOSTS = {"claude": "api.anthropic.com", "openai": "api.openai.com"}
LIST_PATHS = {"claude": "/v1/models?limit=1000", "openai": "/v1/models"}
CALL_PATHS = {"claude": "/v1/messages", "openai": "/v1/chat/completions"}
ANTHROPIC_VERSION = "2023-06-01"
USER_AGENT = "clark"                     # clark: creaite's said "creaite"
ACCOUNT = "clark"                        # the keychain item's account (clark: creaite's was "creaite")
LIST_TIME = 10.0                         # seconds for the whole model list, connecting included
CALL_TIME = 120.0                        # seconds for one answer, as the Claude command's TIME_LIMIT
LIST_CAP = 1_000_000                     # bytes read back at most
CALL_CAP = 4 * ask.MAX_REPLY + 65536     # bytes read back at most for one answer
MAX_SEND = 4 * (ask.MAX_REQUEST + 8000) + 4096    # bytes of request body at most (the request, the rules, the JSON around them)
REPLY_TOKENS = 4096                      # the reply's length, in the provider's tokens, at most
LIST_MAX = 500                           # model ids kept at most
CHUNK = 64 * 1024
MODEL_ID = re.compile(r"[A-Za-z0-9._:-]{1,80}")
FAKE_SWITCH = "CLARK_FAKE_PROVIDERS"
DEV_MARK = ".clark-dev"
REPO = Path(__file__).resolve().parents[2]


class ProviderError(Exception):
    """A provider call that did not give an answer. Holds the provider and an HTTP status (or None), never a key, request or body."""

    def __init__(self, provider, status=None):
        super().__init__(f"{provider}: {status}")
        self.provider, self.status = provider, status


class KeyRefused(ProviderError):
    """401, 403 or another 4xx that is not a limit: the key (or the request) was not accepted."""


class Limited(ProviderError):
    """429, or the provider's own "over the limit" answer (FR-66). Never a disconnect, never a switch."""


class Unreachable(ProviderError):
    """No answer: network, TLS, time, a redirect, a 5xx, too much back, or an answer that isn't the expected shape."""


# ----- the key store -----

def folder_id(data_dir):
    """12 hex characters of a hash of the data folder's real path: the keychain item's middle name."""
    return hashlib.sha256(os.path.realpath(str(data_dir)).encode("utf-8")).hexdigest()[:12]


class KeyStore:
    """Where provider keys live. `has` says whether there is one (never reads it); `put` keeps one; `remove` deletes it (True when it
    is gone afterwards); `peek` reads it for the provider call itself and nothing else, or None."""

    def has(self, provider):
        raise NotImplementedError

    def put(self, provider, key):
        raise NotImplementedError

    def remove(self, provider):
        raise NotImplementedError

    def peek(self, provider):
        raise NotImplementedError


class KeychainStore(KeyStore):
    """The Mac's keychain (platform.keychain_*). On any other system platform raises NotBuiltYet, which reads as "not connected"."""

    def __init__(self, data_dir):
        self.id = folder_id(data_dir)

    def service(self, provider):
        if provider not in PROVIDERS:
            raise ValueError("not a provider")
        return f"clark.ai.{self.id}.{provider}"

    def has(self, provider):
        return platform.keychain_has(self.service(provider), ACCOUNT)

    def put(self, provider, key):
        return platform.keychain_save(self.service(provider), ACCOUNT, key)

    def remove(self, provider):
        return platform.keychain_remove(self.service(provider), ACCOUNT)

    def peek(self, provider):
        return platform.keychain_read(self.service(provider), ACCOUNT)


class MemoryStore(KeyStore):
    """Fake mode and tests only: keys in this process's memory, never on disk."""

    def __init__(self):
        self.keys = {}

    def has(self, provider):
        return provider in self.keys

    def put(self, provider, key):
        if provider not in PROVIDERS or not isinstance(key, str) or not platform.KEYCHAIN_SECRET.fullmatch(key):
            raise ValueError("not a key that can be kept")
        self.keys[provider] = key
        return True

    def remove(self, provider):
        self.keys.pop(provider, None)
        return True

    def peek(self, provider):
        return self.keys.get(provider)


# ----- the network -----

def key_headers(provider, key):
    """The one header that carries the key (and Anthropic's version header, which holds no secret)."""
    if provider == "claude":
        return {"x-api-key": key, "anthropic-version": ANTHROPIC_VERSION}
    return {"Authorization": f"Bearer {key}"}


def tls_context():
    """The system's trusted certificates, the host name checked, TLS 1.2 or later."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    if ctx.minimum_version in (ssl.TLSVersion.MINIMUM_SUPPORTED, ssl.TLSVersion.SSLv3, ssl.TLSVersion.TLSv1, ssl.TLSVersion.TLSv1_1):
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        """Never follow a redirect: urllib then raises the 3xx as an HTTPError, which is "couldn't reach". The key is not sent again."""
        return None


def request_body(provider, model, system, text):
    """The JSON body of one question: the same `system` and `text` for both providers, in each provider's own envelope (FR-67). No tools,
    no files, one user message. OpenAI is told not to store it."""
    if provider == "claude":
        body = {"model": model, "max_tokens": REPLY_TOKENS, "system": system, "messages": [{"role": "user", "content": text}]}
    elif provider == "openai":
        body = {"model": model, "max_completion_tokens": REPLY_TOKENS, "store": False,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": text}]}
    else:
        raise ValueError("not a provider")
    return json.dumps(body, ensure_ascii=False).encode("utf-8")


def reply_text(provider, data):
    """The answer's text from a provider's JSON reply; Unreachable when it isn't one plain text answer."""
    try:
        got = json.loads(data.decode("utf-8"))
        if provider == "claude":
            blocks = got["content"]
            if not isinstance(blocks, list) or not blocks or any(not isinstance(b, dict) or b.get("type") != "text" for b in blocks):
                raise ValueError("not text only")
            text = "".join(b["text"] for b in blocks)
        else:
            text = got["choices"][0]["message"]["content"]
    except Exception:  # noqa: BLE001  anything else is not an answer; nothing of it is kept
        raise Unreachable(provider) from None
    if not isinstance(text, str) or not text.strip():
        raise Unreachable(provider)
    return text


def model_ids(provider, data):
    """The model ids in a model list ({"data": [{"id": ...}, ...]}), at most LIST_MAX."""
    try:
        rows = json.loads(data.decode("utf-8"))["data"]
        ids = [m["id"] for m in rows if isinstance(m, dict) and isinstance(m.get("id"), str) and MODEL_ID.fullmatch(m["id"])]
    except Exception:  # noqa: BLE001
        raise Unreachable(provider) from None
    return ids[:LIST_MAX]


def judge(provider, status):
    """Raise for any status but 200: 429 is a limit, another 4xx a refusal, anything else no answer."""
    if status == 200:
        return
    if status == 429:
        raise Limited(provider, status)
    if isinstance(status, int) and 400 <= status < 500:
        raise KeyRefused(provider, status)
    raise Unreachable(provider, status)


class Https:
    """The real calls. Production code never gives a host or a context: `base` is a method that only a TEST subclass overrides (clark:
    creaite's constructor took any base address, #53 M8)."""
    scheme = "https"

    def __init__(self):
        self.context = tls_context()

    def base(self, provider):
        return f"https://{HOSTS[provider]}"

    def opener(self):
        """urllib with no proxy from the environment, no redirect followed, and the verified TLS context."""
        return urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect(), urllib.request.HTTPSHandler(context=self.context))

    def exchange(self, provider, method, path, key, body, limit, cap):
        """(status, at most `cap` bytes of the answer) for one call. The key goes in its one header. Unreachable when there is no answer,
        when the whole call takes over `limit` seconds, or when the answer is over `cap`."""
        if provider not in HOSTS or not isinstance(key, str) or not platform.KEYCHAIN_SECRET.fullmatch(key):
            raise KeyRefused(provider, None)
        if body is not None and len(body) > MAX_SEND:
            raise ValueError("too much to send")
        url = self.base(provider) + path
        if urllib.parse.urlsplit(url).scheme != self.scheme:
            raise Unreachable(provider)
        headers = {**key_headers(provider, key), "Accept": "application/json", "User-Agent": USER_AGENT}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, method=method, headers=headers)
        deadline = time.monotonic() + limit
        try:
            send = self.opener().open           # (a name of its own: not a text-file open)
            with send(req, timeout=limit) as r:
                return r.status, self.read(r, deadline, cap, provider)
        except urllib.error.HTTPError as e:      # the body of a refusal is never read: it is not shown or kept
            e.close()
            return e.code, b""
        except ProviderError:
            raise
        except Exception:  # noqa: BLE001  network, TLS, time, a broken answer: the provider and nothing else
            raise Unreachable(provider) from None
        finally:
            key = headers = req = None

    @staticmethod
    def read(r, deadline, cap, provider):
        """Read the answer in pieces; the time left is checked before each one and, where the socket is still reachable, each read waits at
        most that long (clark: a total limit, not only per read, #53 M3a). A slow trickle is ended by the check between pieces."""
        sock = getattr(getattr(getattr(r, "fp", None), "raw", None), "_sock", None)
        out = bytearray()
        while True:
            left = deadline - time.monotonic()
            if left <= 0:
                raise Unreachable(provider)
            if sock is not None:
                try:
                    sock.settimeout(left)
                except OSError:                  # the connection handed its socket to the reader and closed its own: the open's limit stands
                    sock = None
            piece = r.read1(CHUNK) if hasattr(r, "read1") else r.read(CHUNK)
            if not piece:
                return bytes(out)
            out += piece
            if len(out) > cap:
                raise Unreachable(provider)

    def models(self, provider, key):
        """The model ids the key can use (Connect tests the key with this)."""
        status, data = self.exchange(provider, "GET", LIST_PATHS[provider], key, None, LIST_TIME, LIST_CAP)
        judge(provider, status)
        return model_ids(provider, data)

    def complete(self, provider, model, system, text, key):
        """One question, no tools: the reply's text."""
        if not isinstance(model, str) or not MODEL_ID.fullmatch(model):
            raise ValueError("not a model id")
        status, data = self.exchange(provider, "POST", CALL_PATHS[provider], key, request_body(provider, model, system, text),
                                     CALL_TIME, CALL_CAP)
        judge(provider, status)
        return reply_text(provider, data)


class FakeHttps(Https):
    """Fake mode only (and tests): no network. A key starting "fake-good" works, "fake-net" can't be reached, "fake-limit" lists models
    but is over its limit when asked, and anything else is refused (401). Keys in tests all end in TESTONLY."""
    FOUND = {"openai": ["gpt-fake-large", "gpt-fake-small", "text-embedding-fake"],
             "claude": ["claude-opus-fake", "claude-sonnet-fake", "claude-haiku-fake"]}
    ANSWER = "The report does not say."

    def __init__(self):
        self.context = None
        self.sent = []

    def _check(self, provider, key, asking=False):
        if key.startswith("fake-net"):
            raise Unreachable(provider)
        if key.startswith("fake-limit") and asking:
            raise Limited(provider, 429)
        if not key.startswith(("fake-good", "fake-limit")):
            raise KeyRefused(provider, 401)

    def models(self, provider, key):
        self._check(provider, key)
        return list(self.FOUND[provider])

    def complete(self, provider, model, system, text, key):
        self._check(provider, key, asking=True)
        self.sent.append((provider, request_body(provider, model, system, text)))
        return self.ANSWER


def fake_mode(data_dir, environ=None):
    """True only when the switch is on AND (the data folder is inside the system's temporary folder, or the repository has DEV_MARK)."""
    environ = os.environ if environ is None else environ
    if environ.get(FAKE_SWITCH) != "1":
        return False
    tmp = Path(os.path.realpath(tempfile.gettempdir()))
    return (REPO / DEV_MARK).is_file() or tmp in Path(os.path.realpath(str(data_dir))).parents


def backend(data_dir, environ=None):
    """(the key store, the caller) for the live server: the fakes in fake mode, else the keychain and the real calls."""
    if fake_mode(data_dir, environ):
        return MemoryStore(), FakeHttps()
    return KeychainStore(data_dir), Https()


# ----- which provider answers (FR-65, FR-66, FR-67) -----
NOT_SET_UP = "AI isn't set up yet. Connect Claude or OpenAI in Settings › AI, then ask again."
BUSY = "Another question is being answered. Wait for it, or press Stop."
KEY_GONE = "{name}'s key isn't in this Mac's keychain any more, so nothing was sent. Connect {name} again in Settings › AI."
KEY_REFUSED = "{name} did not accept the saved key ({status}), so this wasn't answered. Connect {name} again in Settings › AI."
UNREACHABLE = "clark couldn't reach {name} just now, so this wasn't answered. Check the internet connection and try again."
LIMITED = "{name} says this account has reached its limit, so this wasn't answered. {offer} clark never switches by itself."
OFFER_OTHER = "You can choose {other} or a smaller model in Settings › AI, or wait and ask again."
OFFER_SMALLER = "You can choose a smaller model in Settings › AI, or wait and ask again."
# PENDING THE OWNER'S RULING (#55 option b, the owner, 03-11-2026): OpenAI only for projects explicitly marked OK for other providers. No such mark
# exists yet, so OpenAI is never sent a question; this line says so. The wording is the builder's, for the owner to approve.
OPENAI_NOT_MARKED = ("OpenAI is used only for projects marked OK for another provider, and this project isn't, so nothing was sent. "
                     "Choose a Claude model in Settings › AI.")
KEY_READY = "{name} is connected with an API key. Your question and the parts of the report it needs are sent to {name}."


class _EitherLock:
    """`locked()` is true while the command or a direct call is running (ai_service.busy looks at it)."""

    def __init__(self, *locks):
        self.locks = locks

    def locked(self):
        return any(lock.locked() for lock in self.locks if lock is not None)


class Router(ask.Provider):
    """The one provider ask clark and the AI menu use. `choice()` says what is chosen now: None (nothing saved: the Claude command, as
    before #54) or {"provider", "how", "model" (the id the provider takes), "offer_other" (another connected provider's name, or "")}.
    `command` is the Claude command (ask_claude.ClaudeCommand); `store` and `https` are the key store and the caller. It never picks
    a provider by what the text says, and never switches by itself: a limit is reported with an offer, and the choice stays."""
    provider = "router"

    def __init__(self, choice, command, store, https):
        self.choice, self.command, self.store, self.https = choice, command, store, https
        self.direct_lock = threading.Lock()
        self.lock = _EitherLock(getattr(command, "lock", None), self.direct_lock)
        self.stop_event = threading.Event()
        self.owner = None

    def pick(self):
        try:
            got = self.choice()
        except Exception:  # noqa: BLE001  a choice that can't be read sends nothing
            return {"provider": "", "how": ""}
        return got

    def _key_status(self, provider):
        try:
            there = self.store.has(provider)
        except Exception:  # noqa: BLE001  NotBuiltYet off a Mac, a locked keychain: not connected
            there = False
        name = NAMES[provider]
        return {"connected": True, "why": KEY_READY.format(name=name)} if there else {"connected": False, "why": KEY_GONE.format(name=name)}

    def status(self):
        pick = self.pick()
        if pick is None or (pick.get("provider") == "claude" and pick.get("how") == "subscription"):
            return self.command.status()
        if pick.get("provider") in PROVIDERS and pick.get("how") == "key":
            return self._key_status(pick["provider"])
        return {"connected": False, "why": NOT_SET_UP}

    def limit_words(self, provider, other):
        offer = OFFER_OTHER.format(other=other) if other else OFFER_SMALLER
        return LIMITED.format(name=NAMES[provider], offer=offer)

    def ask(self, request):
        pick = self.pick()
        from clark import ask_claude
        if pick is None or (pick.get("provider") == "claude" and pick.get("how") == "subscription"):
            got = self.command.ask(request)
            if isinstance(got, ask.Failure) and got.message == ask_claude.LIMITED:
                return ask.Failure(self.limit_words("claude", (pick or {}).get("offer_other", "")))
            return got
        if pick.get("provider") not in PROVIDERS or pick.get("how") != "key":
            return ask.Failure(NOT_SET_UP)
        if pick["provider"] == "openai":
            return ask.Failure(OPENAI_NOT_MARKED)
        return self.direct(pick, request)

    def direct(self, pick, request):
        """One question to a provider by its API key: the same request text and rules the command gets, in the provider's envelope."""
        from clark import ask_claude                 # the fixed-rules check is the command's own (one list of allowed rules)
        provider, name = pick["provider"], NAMES[pick["provider"]]
        if not self.direct_lock.acquire(blocking=False):
            return ask.Failure(BUSY)
        self.owner = getattr(request, "owner", None)
        self.stop_event.clear()
        key = None
        try:
            cancel = getattr(request, "cancel", None)
            if cancel is not None and cancel.is_set():
                return ask.Failure(ask.STOPPED)
            system = getattr(request, "system", "")
            if not ask_claude.ClaudeCommand.fixed_rules(system):
                return ask.Failure(ask.BAD_INPUT)
            try:
                key = self.store.peek(provider)
            except Exception:  # noqa: BLE001  the keychain's own words are not kept
                key = None
            if not key:
                return ask.Failure(KEY_GONE.format(name=name))
            try:
                text = self.https.complete(provider, pick["model"], ask.system_prompt(request.canary, system), self.envelope(request.text), key)
            except Limited:
                return ask.Failure(self.limit_words(provider, pick.get("offer_other", "")))
            except KeyRefused as e:
                return ask.Failure(KEY_REFUSED.format(name=name, status=e.status or "refused"))
            except ValueError:
                return ask.Failure(ask.TOO_MUCH)
            except Exception:  # noqa: BLE001  Unreachable, or anything else: the provider's name only
                return ask.Failure(UNREACHABLE.format(name=name))
            if self.stop_event.is_set():
                return ask.Failure(ask.STOPPED)
            return text
        finally:
            key = None
            self.owner = None
            self.direct_lock.release()

    def stop(self, owner=None):
        """Stop the question now being answered. A direct call can't be cut off mid-flight: its answer is dropped as Stopped."""
        if self.direct_lock.locked() and (owner is None or owner is self.owner):
            self.stop_event.set()
            return True
        stop = getattr(self.command, "stop", None)
        return bool(stop(owner=owner)) if callable(stop) else False
