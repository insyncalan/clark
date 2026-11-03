"""ai connect (#446, #54): the logic of GET /api/ai-connect, POST /api/ai-connect, POST /api/ai-disconnect and POST /api/ai-model, the
Settings › AI card, and the choice providers.Router reads for every question. GUARDED: this is where a provider key arrives. server.py
only routes to it.

THE KEY LIVES IN THE MAC'S KEYCHAIN AND NOWHERE ELSE. Connect with a key takes it once, in the body of one local request, tests it
with the provider's model list (providers.Https.models: one call to the provider's fixed host), and only then hands it to the key store
(providers.KeychainStore: service `clark.ai.<data folder id>.<provider>`, account `clark`). It is then dropped. No reply of any route
holds the key or any part of it; the answers are `connected` true or false, and words. A refused key says why (the provider's name and
the HTTP status only, never the key or the provider's reply). The key is read back only by providers.Router, for one call. Disconnect
deletes the keychain item, and a model of that provider that was chosen goes back to the recommended one.

What is kept in settings.json (settings.py) is ordinary words only: how each provider is connected, the model chosen for ask clark,
the models a key may use (their ids), and the weaker models the person said "use it anyway" to. Never a key.

THE MODEL (FR-65). The list shows connected providers only, the recommended model marked and the default. A model that is not the
recommended one asks first (409 `weaker`); the person's "use it anyway" (`accept: true`) is remembered. For the Claude subscription the
model goes to the Claude command as `--model` (ask_claude.MODELS); for a Claude key, as the id the key's model list gave for it.

REFUSALS. A body with any other field, a field of the wrong type, or a key that is not one line of plain key characters is refused (400)
and nothing is kept. A refusal never repeats what it was given. The log holds the provider, "connected" or "disconnected" and the how,
never a key.

Every answer is (status, {ok, ...}); a refusal has a stable `code` and a plain `message`.
"""
import logging
import re
import threading

from clark import ask, ask_claude, platform, providers, settings

LOG = logging.getLogger("clark.ai")

PROVIDERS = providers.PROVIDERS
HOWS = {"claude": ("subscription", "key"), "openai": ("key",)}
HOW_KEYS = {"claude": settings.AI_HOW, "openai": settings.AI_OPENAI_HOW}
OFF = "none"                       # how a provider reads after an explicit Disconnect (so ask clark doesn't fall back to the command)
HOW_WORDS = {"subscription": "Claude subscription", "key": "API key"}
# The models the prototype lists for Claude: (id, words, recommended). The ids are the prototype's; the alias is what the command takes.
MODELS = (("claude-opus", "Claude Opus 5.5", True), ("claude-sonnet", "Claude Sonnet 5.5", False), ("claude-haiku", "Claude Haiku 5.5", False))
MODEL_IDS = tuple(m[0] for m in MODELS)
RECOMMENDED = MODELS[0][0]
OPENAI_PREFIX = "openai:"
OPENAI_MODEL = re.compile(r"(?:gpt-[a-z0-9][a-z0-9.-]{0,40}|o[0-9][a-z0-9.-]{0,40})")
OPENAI_NOT_CHAT = ("audio", "realtime", "tts", "transcribe", "image", "search", "embedding", "instruct", "moderation")
MAX_OPENAI_MODELS = 20
MAX_CLAUDE_IDS = 50
CONNECT_FIELDS = {"provider", "how", "key"}

# The connect box's words (FR-63, FR-65), pinned by a test: passages leave the computer, are billed to that account, and go to either
# provider the same way. the owner approves the exact copy.
CONNECT_NOTE = ("The passages ask clark and the AI menu send go to the provider you connect: they leave this computer and are billed "
                "to that account, the same way for Claude and OpenAI. A key is kept in this Mac's keychain, never in clark's files or "
                "backups, and is never shown again.")

MESSAGES = {
    "bad_request": "That request could not be read. Nothing was changed. Reload the page and try again.",
    "bad_key": "That does not look like a complete key. Check you copied all of it. Nothing was kept.",
    "keychain": "This Mac's keychain could not keep the key just now. Nothing was kept. Try again; if it keeps happening, restart clark.",
    "not_connected": "Connect Claude or OpenAI first. Nothing was changed.",
    "not_offered": "That model isn't in the list. Nothing was changed.",
    "not_signed_in": ask_claude.NOT_SIGNED_IN,
    "cant_save": "That could not be saved. Wait a moment and try again; if it keeps happening, restart clark. Nothing was changed.",
    "cant_remove": "The key could not be taken out of this Mac's keychain just now. It is still connected. Try again.",
    "connected": "{name} connected.",
    "disconnected": "Disconnected; its models are out of the list.",
    "model": "Asking will use that model.",
    "refused": "{name} did not accept this key ({status}). Check you copied all of it and that it hasn't been revoked. Nothing was kept.",
    "limited": "{name} says this key is over its limit ({status}). Nothing was kept. Try again later, or check the account's billing.",
    "unreachable": "clark couldn't reach {name}, so the key wasn't tested or kept. Check the internet connection and try again.",
    "weaker": ("{label} isn't the recommended model. Answers may miss things or get facts wrong more often. "
               "Choose it again with Use it anyway to keep it."),
}


class Words:
    """An `allowed` entry for settings.set_ai_choice that takes a space-separated list of words, each passing `ok`, at most `most`."""

    def __init__(self, ok, most):
        self.ok, self.most = ok, most

    def __contains__(self, value):
        parts = value.split(" ") if isinstance(value, str) else None
        return bool(parts) and len(parts) <= self.most and len(set(parts)) == len(parts) and all(self.ok(p) for p in parts)


def _is_model(value):
    return value in MODEL_IDS or (value.startswith(OPENAI_PREFIX) and bool(OPENAI_MODEL.fullmatch(value[len(OPENAI_PREFIX):])))


ALLOWED = {settings.AI_HOW: HOWS["claude"] + (OFF,), settings.AI_OPENAI_HOW: HOWS["openai"] + (OFF,),
           settings.AI_MODEL: Words(_is_model, 1),
           settings.AI_OPENAI_MODELS: Words(lambda v: bool(OPENAI_MODEL.fullmatch(v)), MAX_OPENAI_MODELS),
           settings.AI_CLAUDE_IDS: Words(lambda v: bool(providers.MODEL_ID.fullmatch(v)), MAX_CLAUDE_IDS),
           settings.AI_ACCEPTED: Words(_is_model, 1 + len(MODEL_IDS) + MAX_OPENAI_MODELS)}


def chat_models(ids):
    """The OpenAI ids a question can go to: chat models only, in the order listed, at most MAX_OPENAI_MODELS."""
    out = []
    for i in ids:
        if isinstance(i, str) and OPENAI_MODEL.fullmatch(i) and not any(w in i for w in OPENAI_NOT_CHAT) and i not in out:
            out.append(i)
    return out[:MAX_OPENAI_MODELS]


def alias(model_id):
    """The Claude command's alias for one of MODELS ("claude-opus" -> "opus"), else None."""
    return model_id.split("-", 1)[1] if model_id in MODEL_IDS else None


def chosen_model(data_dir):
    """The model id saved for ask clark, or "" when none."""
    return settings.ai_choice(data_dir, settings.AI_MODEL, ALLOWED[settings.AI_MODEL])


class AiConnect:
    """`data_dir` holds settings.json; `provider` is the Claude command (its status says whether the Claude sign-in is there);
    `store` and `https` are the key store and the provider caller (providers.backend; tests give fakes)."""

    def __init__(self, data_dir, provider=None, store=None, https=None):
        self.data_dir = data_dir
        self.provider = provider
        if store is None or https is None:
            real_store, real_https = providers.backend(data_dir)
            store, https = store or real_store, https or real_https
        self.store, self.https = store, https
        self.lock = threading.Lock()

    def fail(self, code, message=None, **more):
        return {"ok": False, "code": code, "message": message or MESSAGES[code], **more}

    # ----- what is true now -----
    def _words(self, key):
        return settings.ai_choice(self.data_dir, key, ALLOWED[key])

    def how(self, provider):
        """"subscription", "key" (only while the keychain has the item) or "": never an error."""
        how = self._words(HOW_KEYS[provider])
        if how == "key":
            try:
                return "key" if self.store.has(provider) else ""
            except Exception:  # noqa: BLE001  NotBuiltYet off a Mac, or a keychain that can't be asked: not connected
                return ""
        return how if how in HOWS[provider] else ""

    def models(self, hows=None):
        """[{id, label, provider, recommended}] for the connected providers only."""
        hows = hows or {p: self.how(p) for p in PROVIDERS}
        out = []
        if hows["claude"]:
            out += [{"id": i, "label": t, "provider": "claude", "recommended": r} for i, t, r in MODELS]
        if hows["openai"]:
            ids = (self._words(settings.AI_OPENAI_MODELS) or "").split()
            out += [{"id": OPENAI_PREFIX + i, "label": f"OpenAI {i}", "provider": "openai", "recommended": False} for i in ids if i]
        return out

    def current(self, models):
        """The model in use: the saved one when it is in the list, else the recommended one (else the first), else ""."""
        saved, ids = chosen_model(self.data_dir), [m["id"] for m in models]
        if saved in ids:
            return saved
        return next((m["id"] for m in models if m["recommended"]), ids[0] if ids else "")

    def listing(self):
        hows = {p: self.how(p) for p in PROVIDERS}
        models = self.models(hows)
        accepted = (self._words(settings.AI_ACCEPTED) or "").split()
        return {"ok": True, "connected": any(hows.values()), "model": self.current(models), "models": models, "note": CONNECT_NOTE,
                "accepted": [a for a in accepted if a in {m["id"] for m in models}],
                "claude": {"connected": bool(hows["claude"]), "how": hows["claude"]},
                "openai": {"connected": bool(hows["openai"]), "how": hows["openai"], "chatgpt": "later"}}

    def choice(self):
        """For providers.Router, for each question: None when nothing was ever chosen (the Claude command, as before #54), else
        {"provider", "how", "model", "offer_other"}. Never raises; never holds a key."""
        saved = {p: self._words(HOW_KEYS[p]) for p in PROVIDERS}
        if not any(saved.values()):
            return None
        hows = {p: self.how(p) for p in PROVIDERS}
        models = self.models(hows)
        model = self.current(models)
        if not model:
            return {"provider": "", "how": "", "model": "", "offer_other": ""}
        provider = "claude" if model in MODEL_IDS else "openai"
        other = next((providers.NAMES[p] for p in PROVIDERS if p != provider and hows[p]), "")
        if provider == "openai":
            api = model[len(OPENAI_PREFIX):]
        elif hows["claude"] == "key":
            word = alias(model)
            ids = (self._words(settings.AI_CLAUDE_IDS) or "").split()
            api = next((i for i in ids if word in i), "")
        else:
            api = alias(model)
        return {"provider": provider, "how": hows[provider], "model": api, "offer_other": other}

    def command_model(self):
        """The alias the Claude command is given (ask_claude.ClaudeCommand's `model`), or None."""
        pick = self.choice()
        return pick["model"] if pick and pick["provider"] == "claude" and pick["how"] == "subscription" else None

    def get(self, *_ignored):
        with self.lock:
            return 200, self.listing()

    # ----- POST /api/ai-connect -----
    @staticmethod
    def read_connect(body):
        """(provider, how, key) or None for a body of the wrong shape."""
        if not isinstance(body, dict) or not {"provider", "how"} <= set(body) or not set(body) <= CONNECT_FIELDS:
            return None
        provider, how = body["provider"], body["how"]
        if not isinstance(provider, str) or provider not in PROVIDERS or not isinstance(how, str) or how not in HOWS[provider]:
            return None
        if how == "subscription":
            return (provider, how, None) if set(body) == {"provider", "how"} else None
        return (provider, how, body["key"]) if set(body) == CONNECT_FIELDS and isinstance(body["key"], str) else None

    def connect(self, body):
        got = self.read_connect(body)
        body = None                                # the key is held in `key` only, from here, and dropped at the end
        if got is None:
            return 400, self.fail("bad_request")
        provider, how, key = got
        got = None
        name = providers.NAMES[provider]
        if how == "key" and not platform.KEYCHAIN_SECRET.fullmatch(key):
            return 400, self.fail("bad_key")
        with self.lock:
            more = {}
            try:
                if how == "key":
                    try:
                        ids = self.https.models(provider, key)
                    except providers.Limited as e:
                        return 200, self.fail("limited", MESSAGES["limited"].format(name=name, status=e.status), connected=False)
                    except providers.KeyRefused as e:
                        return 200, self.fail("refused", MESSAGES["refused"].format(name=name, status=e.status or 400), connected=False)
                    except Exception:  # noqa: BLE001  Unreachable, or anything else: no words of it are kept
                        return 200, self.fail("unreachable", MESSAGES["unreachable"].format(name=name), connected=False)
                    if provider == "openai":
                        more[settings.AI_OPENAI_MODELS] = " ".join(chat_models(ids))
                    else:
                        more[settings.AI_CLAUDE_IDS] = " ".join([i for i in ids if any(alias(m) in i for m in MODEL_IDS)][:MAX_CLAUDE_IDS])
                    if not self.store.put(provider, key):
                        return 200, self.fail("keychain", connected=False)
                else:
                    state = ask.answer_status(self.provider) if self.provider is not None else {"connected": False, "why": ""}
                    if not state["connected"]:
                        return 200, self.fail("not_signed_in", state["why"] or None, connected=False)
                    self.store.remove(provider)    # a key kept before is not left behind when the sign-in is used instead
            except Exception:  # noqa: BLE001  whatever the key store raised: its words could hold the key, so none are kept or logged
                return 200, self.fail("keychain", connected=False)
            finally:
                key = None
            try:
                settings.set_ai_choice(self.data_dir, {HOW_KEYS[provider]: how, **{k: v for k, v in more.items()}}, ALLOWED)
                if not chosen_model(self.data_dir):
                    first = self.current(self.models())
                    if first:
                        settings.set_ai_choice(self.data_dir, {settings.AI_MODEL: first}, ALLOWED)
            except (ValueError, OSError, platform.PlatformError):
                return 200, self.fail("cant_save", connected=False)
            LOG.info("ai connect: %s connected how=%s", provider, how)
            return 200, {**self.listing(), "message": MESSAGES["connected"].format(name=name)}

    # ----- POST /api/ai-disconnect -----
    def disconnect(self, body):
        if not isinstance(body, dict) or set(body) != {"provider"} or not isinstance(body["provider"], str) or body["provider"] not in PROVIDERS:
            return 400, self.fail("bad_request")
        provider = body["provider"]
        with self.lock:
            try:
                if not self.store.remove(provider):
                    return 409, self.fail("cant_remove", connected=True)
            except platform.NotBuiltYet:
                pass                               # off a Mac there is no keychain item to remove
            except Exception:  # noqa: BLE001
                return 409, self.fail("cant_remove", connected=True)
            changes = {HOW_KEYS[provider]: OFF}
            if provider == "openai":
                changes[settings.AI_OPENAI_MODELS] = ""
            else:
                changes[settings.AI_CLAUDE_IDS] = ""
            try:
                settings.set_ai_choice(self.data_dir, changes, ALLOWED)
                left = self.models()
                ids = {m["id"] for m in left}
                after = {settings.AI_MODEL: chosen_model(self.data_dir) if chosen_model(self.data_dir) in ids else ""}
                if not after[settings.AI_MODEL]:      # anything set to that provider's models goes back to the recommended model
                    after[settings.AI_MODEL] = self.current(left)
                after[settings.AI_ACCEPTED] = " ".join(a for a in (self._words(settings.AI_ACCEPTED) or "").split() if a in ids)
                settings.set_ai_choice(self.data_dir, after, ALLOWED)
            except (ValueError, OSError, platform.PlatformError):
                return 409, self.fail("cant_save")
            LOG.info("ai connect: %s disconnected", provider)
            return 200, {**self.listing(), "message": MESSAGES["disconnected"]}

    # ----- POST /api/ai-model -----
    def model(self, body):
        if (not isinstance(body, dict) or not {"model"} <= set(body) or not set(body) <= {"model", "accept"}
                or not isinstance(body["model"], str) or not _is_model(body["model"])
                or ("accept" in body and body["accept"] is not True)):
            return 400, self.fail("bad_request")
        wanted = body["model"]
        with self.lock:
            models = self.models()
            if not models:
                return 409, self.fail("not_connected")
            row = next((m for m in models if m["id"] == wanted), None)
            if row is None:
                return 409, self.fail("not_offered")
            accepted = (self._words(settings.AI_ACCEPTED) or "").split()
            changes = {settings.AI_MODEL: wanted}
            if not row["recommended"] and wanted not in accepted:
                if body.get("accept") is not True:
                    return 409, self.fail("weaker", MESSAGES["weaker"].format(label=row["label"]), ask=True)
                changes[settings.AI_ACCEPTED] = " ".join(accepted + [wanted])
            try:
                settings.set_ai_choice(self.data_dir, changes, ALLOWED)
            except (ValueError, OSError, platform.PlatformError):
                return 409, self.fail("cant_save")
            return 200, {**self.listing(), "message": MESSAGES["model"]}
