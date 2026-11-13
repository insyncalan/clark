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
RECOMMENDED = {CLAUDE: "sonnet", CHATGPT: ai_codex.RECOMMENDED}     # the owner, 04-11-2026: the default for Claude is always Sonnet; ChatGPT's is the one that compares with it
SMALLER = ("haiku", *ai_codex.SMALLER)              # ask first; the others are simply offered
LABELS = {**{m: f"Claude {ask_claude.MODEL_NAMES[m]}" for m in ask_claude.MODELS}, **ai_codex.MODEL_NAMES}
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


def log_check(name, provider):
    """The Debug-level line for a Connect that failed: which check the provider's command failed, in fixed plain words. Nothing from
    the command, the computer or the person is in it (no path, no output, no name), so one line is always one line. Written for any
    provider that says which check failed (failed_check), and for no other."""
    try:
        code = provider.failed_check()
    except Exception:  # noqa: BLE001
        return
    if code == "not_found":
        LOG.debug("ai: connect failed, the command was not found")
    elif code == "not_mac":
        LOG.debug("ai: connect failed, the command is not a Mac program")
    elif code == "owner":
        LOG.debug("ai: connect failed, the command has the wrong owner or can be changed by others")
    elif code == "unreadable":
        LOG.debug("ai: connect failed, the command could not be read")
    elif code == "version_flags":
        LOG.debug("ai: connect failed, the command's version or options are not supported")
    elif code == "untested":
        LOG.debug("ai: connect failed, the command's version has not been tested with clark")
    elif code == "no_login":
        LOG.debug("ai: connect failed, the command is not signed in with the account clark can use")
    elif code == "api_key":
        LOG.debug("ai: connect failed, the command is signed in with an API key")
    elif code == "login_unreadable":
        LOG.debug("ai: connect failed, the sign-in check gave no usable answer")
    elif code == "container":
        LOG.debug("ai: connect failed, clark is running in a container")
    elif code == "not_mac_os":
        LOG.debug("ai: connect failed, this computer is not a Mac")
    elif code == "odd_home":
        LOG.debug("ai: connect failed, the home folder is not where macOS keeps it")
    elif code is not None:
        LOG.debug("ai: connect failed, a check did not pass")


def fail(status, code, message):
    return status, {"ok": False, "code": code, "message": message}


class AiConnect:
    """`data_dir` holds settings.json. `claude` and `chatgpt` are the providers (ai_providers.Subscription); each one's status says whether the person is
    signed in."""

    def __init__(self, data_dir, claude, chatgpt):
        self.data_dir = data_dir
        self.providers = {CLAUDE: claude, CHATGPT: chatgpt}
        self.lock = threading.Lock()         # a choice is read and saved as one step, so two at once can't lose one

    def provider_of(self, model):
        return next((name for name, p in self.providers.items() if model in p.models()), None)

    def is_on(self, name, saved=None):
        saved = settings.ai_read(self.data_dir) if saved is None else saved
        return saved["chatgpt_on"] if name == CHATGPT else not saved["claude_off"]

    # ----- what the provider chain reads, for every question -----
    def pick(self):
        """(provider, model, prefer) for the next question, or None when nothing is connected. `prefer`: the model is only the default."""
        saved = settings.ai_read(self.data_dir)
        owner = self.provider_of(saved["model"])
        ok = saved["model"] not in SMALLER or saved["model"] in saved["accepted"]     # a smaller model nobody said yes to (a hand-edited file) isn't a choice
        if owner is not None and ok and self.is_on(owner, saved):
            return self.providers[owner], saved["model"], False
        for name in (CLAUDE, CHATGPT):
            if self.is_on(name, saved):
                return self.providers[name], RECOMMENDED[name], True
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
                models += [{"id": m, "label": LABELS[m], "provider": name, "recommended": m == RECOMMENDED[name]} for m in provider.models()]
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
        st = ask.answer_status(self.providers[name])
        if not st["connected"]:
            log_check(name, self.providers[name])
            return fail(409, "not_signed_in", st["why"])
        with self.lock:
            saved = settings.ai_read(self.data_dir)
            before = self.pick()
            changes = {"claude_off": False} if name == CLAUDE else {"chatgpt_on": True}
            alone = before is None or not ask.answer_status(before[0])["connected"]     # nothing else can answer: this one does, without a second step
            if alone and self.provider_of(saved["model"]) != name:
                changes["model"] = RECOMMENDED[name]
            words = CONNECTED.format(model=LABELS[changes["model"]]) if "model" in changes else (
                CONNECTED.format(model=LABELS[before[1]]) if before[0] is self.providers[name] else CONNECTED_OTHER)
            return self._save(changes, words, f"{name} connected")

    def disconnect(self, body):
        name = self.named(body)
        if name is None:
            return fail(400, "bad_request", BAD)
        if name not in self.providers:
            return fail(400, "no_provider", NO_PROVIDER)
        with self.lock:
            changes = {"claude_off": True} if name == CLAUDE else {"chatgpt_on": False}
            if self.provider_of(settings.ai_read(self.data_dir)["model"]) == name:
                changes["model"] = ""                # a model of this provider goes with it, so nothing moves back without being chosen
            got = self._save(changes, DISCONNECTED.format(name=self.providers[name].label), f"{name} disconnected")
        if got[0] == 200:
            self.providers[name].stop()              # a question running on it ends: Disconnect means now
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
            if model in SMALLER and model not in accepted:
                if "accept" not in body:
                    return fail(409, "weaker", WEAKER.format(model=LABELS[model]))
                changes["accepted"] = sorted({*accepted, model})
            return self._save(changes, USING.format(model=LABELS[model]), "model chosen")

    def _save(self, changes, message, what):
        try:
            settings.ai_write(self.data_dir, changes)
        except (ValueError, OSError):
            return fail(409, "unreadable", settings.AI_UNREADABLE)
        LOG.info("ai: %s", what)
        return 200, self.view(message)


def chain(data_dir, claude=None, chatgpt=None):
    """(AiConnect, the provider ask clark uses): both subscriptions, with the choice in Settings › AI applied to every question."""
    claude = claude if claude is not None else ai_providers.ClaudeSubscription()
    chatgpt = chatgpt if chatgpt is not None else ai_providers.ChatGPTSubscription()
    connect = AiConnect(data_dir, claude, chatgpt)
    return connect, ai_providers.Chosen((claude, chatgpt), connect.pick, OFF_WORDS)
