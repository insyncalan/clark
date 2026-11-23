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
import time

from clark import ai_codex, ai_providers, ask, ask_claude, platform, settings

LOG = logging.getLogger("clark.ai_connect")
CLAUDE, CHATGPT = ask_claude.PROVIDER, ai_codex.PROVIDER
RECOMMENDED = {CLAUDE: "sonnet", CHATGPT: ai_codex.RECOMMENDED}     # the owner, 04-11-2026: the default for Claude is always Sonnet; ChatGPT's is the one that compares with it
SMALLER = ("haiku", *ai_codex.SMALLER)              # ask first; the others are simply offered
LABELS = {**{m: f"Claude {ask_claude.MODEL_NAMES[m]}" for m in ask_claude.MODELS}, **ai_codex.MODEL_NAMES}
OFF_WORDS = "Nothing is connected in Settings. Connect Claude or ChatGPT there to use this."
CARD_INTRO = ("Connect Claude or ChatGPT for ask clark: the passages it sends leave this computer, go to the one you choose and count against that plan. "
              "No password or key is kept.")
PROFILE_LINE = "Your profile name is sent to the model with each question."     # row 1331: shown only while a profile name is saved (no name, nothing sent)
CONNECTED = "Connected. Asking can use its models."          # row 1294 (A8): turning a model on connects it; the words are the approved ones
CONNECTED_OTHER = CONNECTED
NOT_SIGNED_IN = {CHATGPT: "ChatGPT is not signed in on this computer. Sign in to the Codex command, then turn it on again."}     # row 1294: the switch goes back off and says this; Claude says what its own check found
SIZE_LINE = ("Size of one question: about {tokens:,} tokens ({chars:,} characters of passages).")
CHARS_PER_TOKEN = 4                       # the usual rough figure for English; the page says "about"
SIZE_HELP = ("The most that one question sends to the model, counted in tokens (about 4 characters each). A higher number reads more of a big project "
             "and costs more. Each model has its own limit and the lower one applies.")     # the ticket's help line
SIZE_SAVED = "Saved."
QUESTION_CHARS = ask.BUDGET               # row 1294: the page states the size that really cuts a question (ask.BUDGET), so page and code cannot differ; 1,200,000 characters is 300,000 tokens at 4 characters each (the A8 cut), and ask.MAX_REQUEST = BUDGET + 30000 caps the whole request
TEST_QUESTION = "Reply with the one word ready."
TEST_SYSTEM = "You answer in one word."
TEST_FAILED = "{label} did not answer."
TEST_NOTHING = "Turn on Claude or ChatGPT first, then test the connection."
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


class Pinned(ask.Provider):
    """One provider asked with one model, for the connection test: the same call a question makes, with the model clark recommends for it."""

    def __init__(self, provider, model):
        self.provider, self.model = provider, model

    def status(self):
        return self.provider.status()

    def ask(self, request):
        return self.provider.ask(request, self.model, prefer=True)


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
        return {"ok": True, **tiles, "model": model, "models": models, "active": picked[0].label if picked is not None else "", "intro": CARD_INTRO, "profile_line": PROFILE_LINE if settings.profile(self.data_dir)["name"] else "", "size": SIZE_LINE.format(tokens=self.size(), chars=self.size() * CHARS_PER_TOKEN), "size_box": {"value": self.size(), "default": settings.ASK_SIZE_DEFAULT, "min": settings.ASK_SIZE_RANGE[0], "max": settings.ASK_SIZE_RANGE[1], "step": settings.ASK_SIZE_STEP, "help": SIZE_HELP}, "message": message}

    def size(self):
        """Size of one question in tokens, as saved (the one reader, settings.ask_size)."""
        return settings.ask_size(self.data_dir)

    def set_size(self, body):
        """POST /api/providers/size {tokens}: the size of one question, a whole number from 10,000 to 500,000 (row 1293 AP2). Anything else
        is refused with the ticket's sentence and the saved value stays; it is never clamped."""
        tokens = body.get("tokens") if isinstance(body, dict) and set(body) == {"tokens"} else None
        if not isinstance(tokens, int) or isinstance(tokens, bool) or not settings.ASK_SIZE_RANGE[0] <= tokens <= settings.ASK_SIZE_RANGE[1]:
            return fail(400, "bad_size", settings.ASK_SIZE_REFUSAL)
        with self.lock:
            try:
                settings.ai_write(self.data_dir, {"ask_size": tokens})
            except (ValueError, OSError):
                return fail(409, "unreadable", settings.AI_UNREADABLE)
        LOG.info("ai: size of one question set")
        return 200, self.view(SIZE_SAVED)

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
            return fail(409, "not_signed_in", st["why"] if st["why"] == platform.needs_mac_words() else NOT_SIGNED_IN.get(name) or st["why"])
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

    def test(self, body, clock=time.monotonic):
        """Test the connection (row 1294, A8): one short question to each model that is on, and how long each took. It asks the model clark would use
        for that provider and keeps nothing: no question, answer or key is stored or logged. Only the log line says which provider answered."""
        if not isinstance(body, dict) or body:
            return fail(400, "bad_request", BAD)
        results = []
        for name, provider in self.providers.items():
            if not self.view()[name]["connected"]:
                continue
            started = clock()
            got = ask.ask_provider(Pinned(provider, RECOMMENDED[name]), ask.Request(text=TEST_QUESTION, question="", system=TEST_SYSTEM))
            took = round(clock() - started, 1)
            answered = isinstance(got, ask.Reply)
            LOG.info("ai: %s tested, %s", name, "answered" if answered else "no answer")
            results.append({"provider": name, "label": provider.label, "answered": answered, "seconds": took,
                            "message": "" if answered else (got.message if isinstance(got, ask.Failure) else TEST_FAILED.format(label=provider.label))})
        if not results:
            return fail(409, "nothing_on", TEST_NOTHING)
        return 200, {"ok": True, "results": results}

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
