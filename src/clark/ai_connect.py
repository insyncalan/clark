"""ai connect (#54, #446): the logic of Settings › AI. GET /api/providers, and POST /api/providers/connect, /disconnect and
/model. server.py only routes to it. There is no key and no password anywhere in this: a provider is the person's own signed-in
command, so what is kept in settings.json is ordinary words only (whether clark may use Claude, the model chosen, the smaller models the
person said "use it anyway" to).

CONNECT AND DISCONNECT are about clark's use of the command, never the sign-in. clark can't sign a person in, and it must not sign them out:
the same sign-in serves their other work. Connect checks the sign-in and says what to do when there is none. Disconnect only stops clark
using it, and says so. Claude counts as connected from the start when the person is signed in, as it did before this card existed.

THE MODEL (FR-65). The list shows connected providers only, with the recommended model marked and the default. A smaller model asks first
(409 `weaker`); the person's "use it anyway" (`accept: true`) is remembered.

Every answer is (status, {ok, ...}); a refusal has a stable `code` and a plain `message`, and never repeats what it was given. The log holds
the provider and what happened, nothing else.
"""
import logging
import threading

from clark import ai_providers, ask, ask_claude, settings

LOG = logging.getLogger("clark.ai_connect")
RECOMMENDED = "sonnet"                              # the owner, 04-11-2026: the default for Claude is always Sonnet
SMALLER = ("haiku",)                                # asks first; Opus and Fable are not smaller, and are simply offered
LABELS = {m: f"Claude {ask_claude.MODEL_NAMES[m]}" for m in ask_claude.MODELS}
CLAUDE = ask_claude.PROVIDER
OFF_WORDS = "Claude isn't connected in Settings. Connect it there to use this."
CONNECTED = "Connected. Asking will use {model}."
DISCONNECTED = "Disconnected. You're still signed in to Claude on this computer, but clark won't use it."
USING = "Asking will use {model}."
WEAKER = "{model} is smaller than the recommended model, so its answers may be less careful. Use it anyway?"
BAD = "That could not be read. Reload the page and try again."
NO_PROVIDER = "That isn't something clark can connect yet."
NOT_CONNECTED = "Connect Claude first."
CARD_INTRO = "Connect Claude for ask clark: the passages it sends leave this computer, go to Claude and count against your Claude plan. No password or key is kept."


def fail(status, code, message):
    return status, {"ok": False, "code": code, "message": message}


class AiConnect:
    """`data_dir` holds settings.json. `claude` is the Claude provider (ai_providers.ClaudeSubscription), whose status says whether the
    person is signed in."""

    def __init__(self, data_dir, claude):
        self.data_dir, self.claude = data_dir, claude
        self.lock = threading.Lock()         # two saves take turns: each reads the settings file and writes it back

    # ----- what the provider chain reads, for every question -----
    def on(self):
        return not settings.ai_read(self.data_dir)["claude_off"]

    def saved_model(self):
        saved = settings.ai_read(self.data_dir)["model"]
        return saved if saved in ask_claude.MODELS else None

    def model(self):
        return self.saved_model() or RECOMMENDED

    # ----- the card -----
    def view(self, message=""):
        st = ask.answer_status(self.claude)
        connected = st["connected"] and self.on()
        models = [{"id": m, "label": LABELS[m], "recommended": m == RECOMMENDED} for m in ask_claude.MODELS] if connected else []
        return {"ok": True, "claude": {"connected": connected, "signed_in": st["connected"], "why": "" if st["connected"] else st["why"]},
                "openai": {"connected": False, "later": True}, "intro": CARD_INTRO, "model": self.model() if connected else "", "models": models, "message": message}

    def get(self, *_ignored):
        return 200, self.view()

    def connect(self, body):
        if not isinstance(body, dict) or set(body) != {"provider"}:
            return fail(400, "bad_request", BAD)
        if body["provider"] != CLAUDE:
            return fail(400, "no_provider", NO_PROVIDER)
        st = ask.answer_status(self.claude)
        if not st["connected"]:
            return fail(409, "not_signed_in", st["why"])
        return self._save({"claude_off": False}, CONNECTED.format(model=LABELS[self.model()]), "connected")

    def disconnect(self, body):
        if not isinstance(body, dict) or set(body) != {"provider"}:
            return fail(400, "bad_request", BAD)
        if body["provider"] != CLAUDE:
            return fail(400, "no_provider", NO_PROVIDER)
        return self._save({"claude_off": True}, DISCONNECTED, "disconnected")

    def choose(self, body):
        if not isinstance(body, dict) or "model" not in body or not set(body) <= {"model", "accept"} or body.get("accept", True) is not True:
            return fail(400, "bad_request", BAD)
        model = body["model"]
        if not isinstance(model, str) or model not in ask_claude.MODELS:
            return fail(400, "bad_model", ask_claude.MODEL_REFUSED)
        view = self.view()
        if not view["claude"]["connected"]:
            return fail(409, "not_connected", NOT_CONNECTED)
        accepted = settings.ai_read(self.data_dir)["accepted"]
        changes = {"model": model}
        if model in SMALLER and model not in accepted:
            if "accept" not in body:
                return fail(409, "weaker", WEAKER.format(model=LABELS[model]))
            changes["accepted"] = sorted({*accepted, model})
        return self._save(changes, USING.format(model=LABELS[model]), "model chosen")

    def _save(self, changes, message, what):
        try:
            with self.lock:
                settings.ai_write(self.data_dir, changes)
        except (ValueError, OSError):
            return fail(409, "unreadable", settings.AI_UNREADABLE)
        LOG.info("ai: %s %s", CLAUDE, what)
        return 200, self.view(message)


def chain(data_dir, claude=None):
    """(AiConnect, the provider ask clark uses): the Claude subscription, with the choice in Settings › AI applied to every question."""
    claude = claude if claude is not None else ai_providers.ClaudeSubscription()
    connect = AiConnect(data_dir, claude)
    return connect, ai_providers.Chosen(claude, connect.on, connect.saved_model, RECOMMENDED, OFF_WORDS)
