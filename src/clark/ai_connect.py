"""ai connect (#54, #446, #52): the logic of Settings › AI. GET /api/providers, and POST /api/providers/connect, /disconnect and /model. server.py only
routes to it. There is no key and no password anywhere in this: a provider is the person's own signed-in command, so what is kept in settings.json is
ordinary words only (which providers clark may use, the model chosen, the smaller models the person said "use it anyway" to).

CONNECT AND DISCONNECT are about clark's use of the command, never the sign-in. clark can't sign a person in, and it must not sign them out: the same
sign-in serves their other work. Connect checks the sign-in and says what to do when there is none. Disconnect stops clark using it, ends a question
already running on it, and says the sign-in stays. Claude counts as connected from the start when the person is signed in, as it did before this card
existed. ChatGPT is off until the person connects it: what they ask would go to a second company, so that is their choice to make.

THE MODEL (FR-65). The list shows connected providers only, with each one's recommended model marked. The model chosen decides the provider. With none
chosen: Claude's recommended model when Claude is connected, otherwise ChatGPT's. A smaller model asks first (409 `weaker`); the person's "use it anyway"
(`accept: true`) is remembered. clark never moves to another provider by itself.

Every answer is (status, {ok, ...}); a refusal has a stable `code` and a plain `message`, and never repeats what it was given. The log holds the provider
and what happened, nothing else.
"""
import logging
import threading

from clark import ai_codex, ai_providers, ask, ask_claude, settings

LOG = logging.getLogger("clark.ai_connect")
CLAUDE, CHATGPT = ask_claude.PROVIDER, ai_codex.PROVIDER


class Entry:
    """One provider in the registry: everything the card, the choice and the chain need to know about it, so no loop or dict elsewhere names a
    provider. `key` is the saved setting (settings.ai_read's name) and `inverted` says whether ON is the setting being False (claude_off).
    `route` is the kind of provider ("subscription": the person's own signed-in command). `make()` builds the real provider. `check(provider)`
    is the status connecting needs; `after_off(provider)` runs once the setting is saved (a running question ends). A later route overrides these."""
    route = "subscription"

    def __init__(self, name, key, inverted, recommended, labels, smaller, make, route="subscription"):
        self.name, self.key, self.inverted, self.recommended = name, key, inverted, recommended
        self.labels, self.smaller, self.make, self.route = dict(labels), tuple(smaller), make, route

    def is_on(self, saved):
        return bool(saved[self.key]) != self.inverted

    def setting(self, on):
        """The change that turns this provider on or off, in the saved setting's own words."""
        return {self.key: (not on) if self.inverted else bool(on)}

    def check(self, provider):
        return ask.answer_status(provider)

    def after_off(self, provider):
        provider.stop()


REGISTRY = (
    Entry(CLAUDE, "claude_off", True, "sonnet", {m: f"Claude {ask_claude.MODEL_NAMES[m]}" for m in ask_claude.MODELS}, ("haiku",),
          ai_providers.ClaudeSubscription),
    Entry(CHATGPT, "chatgpt_on", False, ai_codex.RECOMMENDED, ai_codex.MODEL_NAMES, ai_codex.SMALLER, ai_providers.ChatGPTSubscription),
)       # the order is the order of the tiles and of the fallback: Claude, then ChatGPT
RECOMMENDED = {e.name: e.recommended for e in REGISTRY}     # the owner, 04-11-2026: the default for Claude is always Sonnet; ChatGPT's is the one that compares with it
SMALLER = tuple(m for e in REGISTRY for m in e.smaller)     # ask first; the others are simply offered
LABELS = {m: label for e in REGISTRY for m, label in e.labels.items()}
OFF_WORDS = "Nothing is connected in Settings. Connect Claude or ChatGPT there to use this."
CARD_INTRO = ("Connect Claude or ChatGPT for ask clark: the passages it sends leave this computer, go to the one you choose and count against that plan. "
              "No password or key is kept.")
CONNECTED = "Connected. Asking will use {model}."
CONNECTED_OTHER = "Connected. Choose one of its models below to use it."
DISCONNECTED = "Disconnected. You're still signed in to {name} on this computer, but clark won't use it."
USING = "Asking will use {model}."
WEAKER = "{model} is smaller than the recommended model, so its answers may be less careful. Use it anyway?"
BAD = "That could not be read. Reload the page and try again."
NO_PROVIDER = "That isn't something clark can connect."
NOT_CONNECTED = "Connect it first."


def fail(status, code, message):
    return status, {"ok": False, "code": code, "message": message}


class AiConnect:
    """`data_dir` holds settings.json. `claude` and `chatgpt` are the providers (ai_providers.Subscription); each one's status says whether the person is
    signed in."""

    def __init__(self, data_dir, claude, chatgpt, registry=REGISTRY, extra=None):
        """`registry` is the ordered tuple of Entry; `extra` maps the name of any entry beyond Claude and ChatGPT to its provider."""
        self.data_dir = data_dir
        given = {CLAUDE: claude, CHATGPT: chatgpt, **(extra or {})}
        self.registry = {e.name: e for e in registry}
        self.providers = {e.name: given[e.name] for e in registry}
        self.recommended = {e.name: e.recommended for e in registry}
        self.smaller = tuple(m for e in registry for m in e.smaller)
        self.labels = {m: label for e in registry for m, label in e.labels.items()}
        self.lock = threading.Lock()         # a choice is read and saved as one step, so two at once can't lose one

    def provider_of(self, model):
        return next((name for name, p in self.providers.items() if model in p.models()), None)

    def is_on(self, name, saved=None):
        saved = settings.ai_read(self.data_dir) if saved is None else saved
        return self.registry[name].is_on(saved)

    # ----- what the provider chain reads, for every question -----
    def pick(self):
        """(provider, model, prefer) for the next question, or None when nothing is connected. `prefer`: the model is only the default."""
        saved = settings.ai_read(self.data_dir)
        owner = self.provider_of(saved["model"])
        ok = saved["model"] not in self.smaller or saved["model"] in saved["accepted"]     # a smaller model nobody said yes to (a hand-edited file) isn't a choice
        if owner is not None and ok and self.is_on(owner, saved):
            return self.providers[owner], saved["model"], False
        for name in self.providers:
            if self.is_on(name, saved):
                return self.providers[name], self.recommended[name], True
        return None

    # ----- the card -----
    def view(self, message=""):
        saved = settings.ai_read(self.data_dir)
        tiles, models = {}, []
        for name, provider in self.providers.items():
            st = ask.answer_status(provider)
            connected = st["connected"] and self.is_on(name, saved)
            tiles[name] = {"connected": connected, "signed_in": st["connected"], "why": "" if st["connected"] else st["why"]}
            if connected:
                models += [{"id": m, "label": self.labels[m], "provider": name, "recommended": m == self.recommended[name]} for m in provider.models()]
        offered = [m["id"] for m in models]
        picked = self.pick()
        model = picked[1] if picked is not None and picked[1] in offered else (offered[0] if offered else "")
        return {"ok": True, **tiles, "model": model, "models": models, "active": picked[0].label if picked is not None else "", "intro": CARD_INTRO, "message": message}

    def get(self, *_ignored):
        return 200, self.view()

    @staticmethod
    def named(body):
        return body["provider"] if isinstance(body, dict) and set(body) == {"provider"} and isinstance(body["provider"], str) else None

    def connect(self, body):
        name = self.named(body)
        if name is None:
            return fail(400, "bad_request", BAD)
        if name not in self.providers:
            return fail(400, "no_provider", NO_PROVIDER)
        st = self.registry[name].check(self.providers[name])
        if not st["connected"]:
            return fail(409, "not_signed_in", st["why"])
        with self.lock:
            saved = settings.ai_read(self.data_dir)
            before = self.pick()
            changes = self.registry[name].setting(True)
            alone = before is None or not ask.answer_status(before[0])["connected"]     # nothing else can answer: this one does, without a second step
            if alone and self.provider_of(saved["model"]) != name:
                changes["model"] = self.recommended[name]
            words = CONNECTED.format(model=self.labels[changes["model"]]) if "model" in changes else (
                CONNECTED.format(model=self.labels[before[1]]) if before[0] is self.providers[name] else CONNECTED_OTHER)
            return self._save(changes, words, f"{name} connected")

    def disconnect(self, body):
        name = self.named(body)
        if name is None:
            return fail(400, "bad_request", BAD)
        if name not in self.providers:
            return fail(400, "no_provider", NO_PROVIDER)
        with self.lock:
            changes = self.registry[name].setting(False)
            if self.provider_of(settings.ai_read(self.data_dir)["model"]) == name:
                changes["model"] = ""                # a model of this provider goes with it, so nothing moves back without being chosen
            got = self._save(changes, DISCONNECTED.format(name=self.providers[name].label), f"{name} disconnected")
        if got[0] == 200:
            self.registry[name].after_off(self.providers[name])              # a question running on it ends: Disconnect means now
        return got

    def choose(self, body):
        if not isinstance(body, dict) or "model" not in body or not set(body) <= {"model", "accept"} or body.get("accept", True) is not True:
            return fail(400, "bad_request", BAD)
        model = body["model"]
        owner = self.provider_of(model) if isinstance(model, str) else None
        if owner is None:
            return fail(400, "bad_model", ask_claude.MODEL_REFUSED)
        if not self.view()[owner]["connected"]:
            return fail(409, "not_connected", NOT_CONNECTED)
        with self.lock:
            accepted = settings.ai_read(self.data_dir)["accepted"]
            changes = {"model": model}
            if model in self.smaller and model not in accepted:
                if "accept" not in body:
                    return fail(409, "weaker", WEAKER.format(model=self.labels[model]))
                changes["accepted"] = sorted({*accepted, model})
            return self._save(changes, USING.format(model=self.labels[model]), "model chosen")

    def _save(self, changes, message, what):
        try:
            settings.ai_write(self.data_dir, changes)
        except (ValueError, OSError):
            return fail(409, "unreadable", settings.AI_UNREADABLE)
        LOG.info("ai: %s", what)
        return 200, self.view(message)


def chain(data_dir, claude=None, chatgpt=None, registry=REGISTRY, extra=None):
    """(AiConnect, the provider ask clark uses): every provider in the registry, with the choice in Settings › AI applied to every question.
    `claude`, `chatgpt` and `extra` ({name: provider}) are seams; any provider not given is built by its entry."""
    given = {CLAUDE: claude, CHATGPT: chatgpt, **(extra or {})}
    built = {e.name: given.get(e.name) if given.get(e.name) is not None else e.make() for e in registry}
    connect = AiConnect(data_dir, built[CLAUDE], built[CHATGPT], registry, {n: p for n, p in built.items() if n not in (CLAUDE, CHATGPT)})
    return connect, ai_providers.Chosen(tuple(built.values()), connect.pick, OFF_WORDS)
