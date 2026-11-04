"""The Mac Keychain store for the two AI keys (#643, slice 1): service `clark-ai`, account `claude` or `openai`. Nothing in clark calls this yet.

THE RULE: a key goes to `security` on its STANDARD INPUT only (`security -i` reads its commands there, as dev/tools/sign_release.py does for the
release key), so it is never in an argv where `ps` could show it. It is never in an environment variable, a log line, an exception message, or
a return value other than `read_key`. Every call to /usr/bin/security goes through the ONE function `run_security`; tests replace it.

Choice the owner can change: items are made with `-T ""`, so no application is trusted, not even `security`, and macOS asks before it gives
a key out. The cost is a macOS prompt on a read. Dropping `-T ""` would trust `security` and remove the prompt, for any program that can run it.

The program is started through platform.run_program (the one place clark may start a program); stdin is handed in as a keyword for that call.
`security -i` exits 0 even when the command inside it fails (it prints `returned -25299`), so save_key also reads the output and checks the item exists.
"""
import functools
import re

from clark import platform

SERVICE = "clark-ai"
PROVIDERS = ("claude", "openai")
SECURITY = "/usr/bin/security"
NOT_FOUND = 44                      # security's exit code for "no such item"
PREFIXES = {"claude": "sk-ant-", "openai": "sk-"}
MIN_LENGTH, MAX_LENGTH = 20, 400
ALLOWED = re.compile(r"[A-Za-z0-9_-]+")     # real Anthropic and OpenAI keys use exactly this alphabet, after their prefix
FAILED_LINE = re.compile(r"returned -?\d+")  # `security -i` exits 0 even when its inner command fails; it prints `returned -25299`
# Short reason codes, by name. Never the key.
REFUSAL_CODES = {"provider": "provider", "empty": "empty", "not_ascii": "not_ascii", "bad_character": "bad_character",
                 "too_short": "too_short", "too_long": "too_long", "wrong_prefix": "wrong_prefix"}

# Internal sentences: never shown anywhere yet, and never holding a key or security's own output.
KEYCHAIN_SAID_NO = "The Keychain could not be used just now. Nothing was changed."
REFUSED_KEY = "That key was refused before it was stored (%s)."
REFUSED_PROVIDER = "That provider is not one clark keeps a key for."
NEEDS_MAC = "The Keychain for AI keys needs the Mac"


class KeychainError(Exception):
    """The Keychain was locked, missing or said no. The text is fixed and never holds a key or security's output."""


class KeyRefused(KeychainError):
    """The key's shape was refused before anything was stored. The text names only the reason code."""


def valid_shape(provider, key):
    """None if `key` could be an API key for `provider`, else a short reason code (REFUSAL_CODES). Never returns or echoes the key.
    An allowlist: the provider's prefix, then only letters, digits, `-` and `_`; 20 to 400 characters."""
    if provider not in PROVIDERS:
        return REFUSAL_CODES["provider"]
    if not isinstance(key, str) or not key:
        return REFUSAL_CODES["empty"]
    if not key.isascii():
        return REFUSAL_CODES["not_ascii"]
    if not ALLOWED.fullmatch(key):
        return REFUSAL_CODES["bad_character"]
    if len(key) < MIN_LENGTH:
        return REFUSAL_CODES["too_short"]
    if len(key) > MAX_LENGTH:
        return REFUSAL_CODES["too_long"]
    if not key.startswith(PREFIXES[provider]):
        return REFUSAL_CODES["wrong_prefix"]
    if provider == "openai" and key.startswith("sk-ant-"):      # an Anthropic key is not an OpenAI key, though it starts with `sk-`
        return REFUSAL_CODES["wrong_prefix"]
    return None


def _ready(provider):
    """Refuse off the Mac and in the container (the Keychain isn't there); refuse a provider clark keeps no key for."""
    platform._only_mac(NEEDS_MAC)
    if platform.container_mode():
        raise platform.NotBuiltYet(NEEDS_MAC + ": the container has no Keychain")
    if provider not in PROVIDERS:
        raise KeychainError(REFUSED_PROVIDER)


def run_security(args, stdin=None):
    """The ONE place the Keychain tool is run: (exit code, standard output, standard error). Tests replace this; nothing else calls
    `security`. Neither output is ever logged or put in an exception."""
    run = functools.partial(platform.subprocess.run, input=stdin, timeout=60)
    try:
        done = platform.run_program([SECURITY] + list(args), run=run)
    finally:
        del run, stdin                  # do not keep the command text in this frame for a traceback to reach
    return done.returncode, done.stdout, done.stderr


def _call(args, stdin=None):
    """run_security, with any failure to even start it turned into the one fixed sentence (no exception text goes on)."""
    try:
        return run_security(args, stdin)
    except Exception:
        raise KeychainError(KEYCHAIN_SAID_NO) from None
    finally:
        del stdin


def has_key(provider):
    """True if a key is stored for `provider`. Reads only the item's existence, not the key, so macOS asks nothing."""
    _ready(provider)
    code = _call(["find-generic-password", "-s", SERVICE, "-a", provider])[0]
    if code == 0:
        return True
    if code == NOT_FOUND:
        return False
    raise KeychainError(KEYCHAIN_SAID_NO)


def save_key(provider, key):
    """Store `key` for `provider`, replacing any earlier one (-U). Refused first if the shape is wrong. Returns None.
    `security -i` exits 0 even when the add fails, so success is: exit 0, no `returned <number>` line in either output, AND the item found."""
    _ready(provider)
    try:
        reason = valid_shape(provider, key)
        if reason:
            raise KeyRefused(REFUSED_KEY % reason)
        # The shape check above allows only letters, digits, `-` and `_`, so the key cannot change the meaning of this command line.
        # The line is built and handed in in one expression, so no local of this function holds it.
        code, out, err = _call(["-i"], stdin='add-generic-password -U -s %s -a %s -T "" -w %s\n' % (SERVICE, provider, key))
    finally:
        del key                         # the key is not left in this frame for a traceback to reach
    if code != 0 or FAILED_LINE.search((out or "") + "\n" + (err or "")):
        raise KeychainError(KEYCHAIN_SAID_NO)
    if not has_key(provider):
        raise KeychainError(KEYCHAIN_SAID_NO)


def read_key(provider):
    """The stored key for `provider`, or None if there is none. The only function that returns a key."""
    _ready(provider)
    code, out, _ = _call(["find-generic-password", "-s", SERVICE, "-a", provider, "-w"])
    if code == NOT_FOUND:
        return None
    if code != 0:
        raise KeychainError(KEYCHAIN_SAID_NO)
    return (out or "").rstrip("\n") or None


def delete_key(provider):
    """Remove the stored key for `provider`; nothing to remove is fine. Returns None."""
    _ready(provider)
    code = _call(["delete-generic-password", "-s", SERVICE, "-a", provider])[0]
    if code not in (0, NOT_FOUND):
        raise KeychainError(KEYCHAIN_SAID_NO)
