"""ai connect (#446): the logic of GET /api/ai-connect, POST /api/ai-connect, POST /api/ai-disconnect and POST /api/ai-model, the
Settings › AI card. GUARDED: this is the one place that holds an AI provider key. server.py only routes to it.

THE KEY LIVES IN THE MAC'S KEYCHAIN AND NOWHERE ELSE. Connect with a key takes it once, in the body of one local request, and hands
it straight to the keychain (platform.keychain_save: standard input, never an argument, an environment, a file or a log). It is then
dropped. No reply of any route holds the key or any part of it, not even its last characters; the answers are `connected` true or
false, and words. The page never has it again. Nothing here reads it back out of the keychain, so nothing in this version sends it
anywhere: the one provider (ask_claude) uses the person's Claude sign-in and refuses an API key. A later provider that does use the key
must read it through a new platform function and send it only to its provider. Disconnect deletes the keychain item.
The item is made with no trusted program, so reading it needs the person's own approval.

What is kept in settings.json (settings.py) is only how Claude is connected ("subscription" or "key") and the model chosen for ask
clark: ordinary words. Whether a key is there is the keychain's answer, asked by description only.

THE MODEL. The choice is stored and offered back; ask clark does not send it yet. It plugs in at ask_claude.ClaudeCommand's argument
list (the one place the command is built): take "--model" out of NEVER_FLAGS and add `--model <alias>` from `chosen_model()` (the id
without "claude-": opus, sonnet or haiku).

REFUSALS. A body with any other field, a field of the wrong type, or a key that is not one line of plain key characters is refused (400)
and nothing is kept. A refusal never repeats what it was given. The log holds the word "connected" or "disconnected" and the how, never a
key.

Every answer is (status, {ok, ...}); a refusal has a stable `code` and a plain `message`.
"""
import logging
import threading

from clark import ask, ask_claude, platform, settings

LOG = logging.getLogger("clark.ai")

PROVIDER = "claude"
HOWS = ("subscription", "key")
HOW_WORDS = {"subscription": "Claude subscription", "key": "API key"}
# The models the prototype lists for Claude: (id, words, recommended). The ids are the prototype's.
MODELS = (("claude-opus", "Claude Opus 5.5", True), ("claude-sonnet", "Claude Sonnet 5.5", False), ("claude-haiku", "Claude Haiku 5.5", False))
MODEL_IDS = tuple(m[0] for m in MODELS)
DEFAULT_MODEL = MODELS[0][0]
ALLOWED = {settings.AI_HOW: HOWS, settings.AI_MODEL: MODEL_IDS}
CONNECT_FIELDS = {"provider", "how", "key"}

SERVICE = "clark-ai-claude"      # the keychain item's two names: fixed words, never from a request
ACCOUNT = "claude-api-key"

MESSAGES = {
    "bad_request": "That request could not be read. Nothing was changed. Reload the page and try again.",
    "bad_key": "That does not look like a complete key. Check you copied all of it. Nothing was kept.",
    "keychain": "This Mac's keychain could not keep the key just now. Nothing was kept. Try again; if it keeps happening, restart clark.",
    "not_connected": "Connect Claude first. Nothing was changed.",
    "not_signed_in": ask_claude.NOT_SIGNED_IN,
    "cant_save": "That could not be saved. Wait a moment and try again; if it keeps happening, restart clark. Nothing was changed.",
    "cant_remove": "The key could not be taken out of this Mac's keychain just now. It is still connected. Try again.",
    "connected": "Claude connected.",
    "disconnected": "Disconnected; its models are out of the list.",
    "model": "Asking will use that model.",
}


class Keychain:
    """The one key, as the Mac's keychain keeps it. A test gives AiConnect a fake with the same three methods."""

    def save(self, secret):
        return platform.keychain_save(SERVICE, ACCOUNT, secret)

    def has(self):
        return platform.keychain_has(SERVICE, ACCOUNT)

    def remove(self):
        return platform.keychain_remove(SERVICE, ACCOUNT)


def chosen_model(data_dir):
    """The model id chosen for ask clark, or "" when none: the saved one when it is one of the listed models."""
    return settings.ai_choice(data_dir, settings.AI_MODEL, MODEL_IDS)


class AiConnect:
    """`data_dir` holds settings.json; `provider` is the one ask provider (its status says whether the Claude sign-in is there);
    `keychain` is a seam for tests."""

    def __init__(self, data_dir, provider=None, keychain=None):
        self.data_dir = data_dir
        self.provider = provider
        self.keychain = keychain or Keychain()
        self.lock = threading.Lock()

    def fail(self, code, message=None, **more):
        return {"ok": False, "code": code, "message": message or MESSAGES[code], **more}

    # ----- what is true now -----
    def how(self):
        """"subscription", "key" (only when the keychain still has the item) or "": never an error."""
        how = settings.ai_choice(self.data_dir, settings.AI_HOW, HOWS)
        if how == "key":
            try:
                return "key" if self.keychain.has() else ""
            except platform.PlatformError:
                return ""
        return how

    def listing(self):
        how = self.how()
        models = [{"id": i, "label": t, "recommended": r} for i, t, r in MODELS] if how else []
        model = chosen_model(self.data_dir) if how else ""
        return {"ok": True, "provider": PROVIDER, "connected": bool(how), "how": how, "model": model or (DEFAULT_MODEL if how else ""),
                "models": models, "openai": {"later": True}}

    def get(self, *_ignored):
        with self.lock:
            return 200, self.listing()

    # ----- POST /api/ai-connect -----
    @staticmethod
    def read_connect(body):
        """(how, key) or None for a body of the wrong shape: exactly provider "claude" and how; and key, a text, when how is "key"."""
        if not isinstance(body, dict) or not {"provider", "how"} <= set(body) or not set(body) <= CONNECT_FIELDS:
            return None
        how = body["how"]
        if body["provider"] != PROVIDER or not isinstance(how, str) or how not in HOWS:
            return None
        if how == "subscription":
            return (how, None) if set(body) == {"provider", "how"} else None
        return (how, body["key"]) if set(body) == CONNECT_FIELDS and isinstance(body["key"], str) else None

    def connect(self, body):
        got = self.read_connect(body)
        body = None                                # the key is held in `key` only, from here, and dropped at the end
        if got is None:
            return 400, self.fail("bad_request")
        how, key = got
        if how == "key" and not platform.KEYCHAIN_SECRET.fullmatch(key):
            return 400, self.fail("bad_key")
        with self.lock:
            try:
                if how == "key":
                    if not self.keychain.save(key):
                        return 200, self.fail("keychain", connected=False)
                else:
                    state = ask.answer_status(self.provider) if self.provider is not None else {"connected": False, "why": ""}
                    if not state["connected"]:
                        return 200, self.fail("not_signed_in", state["why"] or None, connected=False)
                    self.keychain.remove()         # a key kept before is not left behind when the sign-in is used instead
            except Exception:  # noqa: BLE001  whatever the keychain seam raised: its words could hold the key, so none are kept or logged
                return 200, self.fail("keychain", connected=False)
            finally:
                key = got = None
            try:
                settings.set_ai_choice(self.data_dir, {settings.AI_HOW: how}, ALLOWED)
                if not chosen_model(self.data_dir):
                    settings.set_ai_choice(self.data_dir, {settings.AI_MODEL: DEFAULT_MODEL}, ALLOWED)
            except (ValueError, OSError, platform.PlatformError):
                return 200, self.fail("cant_save", connected=False)
            LOG.info("ai connect: claude connected how=%s", how)
            return 200, {**self.listing(), "message": MESSAGES["connected"]}

    # ----- POST /api/ai-disconnect -----
    def disconnect(self, body):
        if body != {"provider": PROVIDER}:
            return 400, self.fail("bad_request")
        with self.lock:
            try:
                if not self.keychain.remove():
                    return 409, self.fail("cant_remove", connected=True)
            except platform.PlatformError:
                return 409, self.fail("cant_remove", connected=True)
            try:
                settings.set_ai_choice(self.data_dir, {settings.AI_HOW: "", settings.AI_MODEL: ""}, ALLOWED)
            except (ValueError, OSError, platform.PlatformError):
                return 409, self.fail("cant_save")
            LOG.info("ai connect: claude disconnected")
            return 200, {**self.listing(), "message": MESSAGES["disconnected"]}

    # ----- POST /api/ai-model -----
    def model(self, body):
        if not isinstance(body, dict) or set(body) != {"model"} or not isinstance(body["model"], str) or body["model"] not in MODEL_IDS:
            return 400, self.fail("bad_request")
        with self.lock:
            if not self.how():
                return 409, self.fail("not_connected")
            try:
                settings.set_ai_choice(self.data_dir, {settings.AI_MODEL: body["model"]}, ALLOWED)
            except (ValueError, OSError, platform.PlatformError):
                return 409, self.fail("cant_save")
            return 200, {**self.listing(), "message": MESSAGES["model"]}
