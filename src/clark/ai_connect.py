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

from clark import ai_codex, ai_providers, ask, ask_claude, ask_words, platform, settings

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
SIZE_LINE = ("Size of one question: about {tokens:,} tokens ({chars:,} characters of passages). Each model has its own limit and the lower one applies.")
CHARS_PER_TOKEN = 4                       # the usual rough figure for English; the page says "about"
QUESTION_CHARS = ask.BUDGET               # row 1294: the page states the size that really cuts a question (ask.BUDGET), so page and code cannot differ; 1,200,000 characters is 300,000 tokens at 4 characters each (the A8 cut), and ask.MAX_REQUEST = BUDGET + 30000 caps the whole request
TEST_QUESTION = "Reply with the one word ready."
TEST_FAILED = "{label} did not answer."
# ---- row 1492: Check again. Connected only after ONE real answered request; a failure is ONE fixed sentence with ONE next step. The words are the approved ones (NEW-WORDS).
VERIFY_LIMIT = 30.0                       # AP3: seconds for the whole Connect (the checks and the one request); a real question has 120
UNCHECKED = "Signed in, not checked yet"
STEPS = {"command": "Checking the command…", "signin": "Checking you are signed in…", "ask": "Asking for one word…"}
CHECKED = "Connected. {label} answered in {seconds} seconds. Checked {at}."
V_NOT_INSTALLED = "{label} is not installed on this computer. Install it, then press Check again."
V_NOT_SIGNED_IN = {CLAUDE: "Claude is not signed in. Open Terminal, type claude, sign in, then press Check again.",
                   CHATGPT: "ChatGPT is not signed in. Open Terminal, type codex login, sign in with ChatGPT, then press Check again."}
V_WRONG_KIND = "{label} is signed in in a way clark can't use. Sign in with your {label} subscription, then press Check again."
V_EXPIRED = "Your {label} sign-in has run out. Sign in again in Terminal, then press Check again."
V_NO_NETWORK = "{label} could not be reached. Check your internet connection, then press Check again."
V_TOO_SLOW = "{label} did not answer within 30 seconds. Press Check again."
V_CANCELLED = "Cancelled. {label} is not connected."
V_CHECK_SLOW = "The check took too long. Press Check again."
V_BUSY = ask_claude.BUSY                  # AP12: busy is told as busy, with the words the Ask panel already uses
V_LIMIT = {CLAUDE: ask_claude.LIMIT_REACHED, CHATGPT: ai_codex.LIMIT_REACHED}
V_UNKNOWN = TEST_FAILED
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
    elif code == "slow":
        LOG.debug("ai: connect failed, a check took too long")
    elif code == "odd_home":
        LOG.debug("ai: connect failed, the home folder is not where macOS keeps it")
    elif code is not None:
        LOG.debug("ai: connect failed, a check did not pass")


class Pinned(ask.Provider):
    """One provider asked with one model, for the connection test: the same call a question makes, with the model clark recommends for it."""

    def __init__(self, provider, model, status=None):
        self.provider, self.model, self.known = provider, model, status

    def status(self):
        """The status already read for this check (row 1492, AP11: one status check per provider); read anew only when none was given."""
        return self.known if self.known is not None else self.provider.status()

    def ask(self, request):
        return self.provider.ask(request, self.model, prefer=True)


def fail(status, code, message):
    return status, {"ok": False, "code": code, "message": message}


class AiConnect:
    """`data_dir` holds settings.json. `claude` and `chatgpt` are the providers (ai_providers.Subscription); each one's status says whether the person is
    signed in."""

    def __init__(self, data_dir, claude, chatgpt):
        self.data_dir = data_dir
        self.owner = object()                # row 1492: the owner of the check's own requests, so Cancel and the deadline stop only those
        self.providers = {CLAUDE: claude, CHATGPT: chatgpt}
        self.lock = threading.Lock()         # a choice is read and saved as one step, so two at once can't lose one
        self.guard = threading.Lock()        # row 1492: the checks running now and what they have shown, in memory only
        self.running = {}                    # provider name -> the Event a Cancel sets
        self.steps = {}                      # provider name -> the step a running check is on
        self.checked = {}                    # provider name -> {"seconds", "at"}: the last check that was answered, since clark started; never saved

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
            if not st["connected"]:
                self.checked.pop(name, None)           # row 1492: signed out, so its last check no longer stands (signing in again reads "not checked yet")
            done = self.checked.get(name) if connected else None
            tiles[name] = {"connected": connected, "signed_in": st["connected"], "why": "" if st["connected"] else st["why"],
                           "checked": done is not None, "checked_line": CHECKED.format(label=provider.label, **done) if done else ""}
            if connected:
                models += [{"id": m, "label": LABELS[m], "provider": name, "recommended": m == RECOMMENDED[name]} for m in provider.models()]
        offered = [m["id"] for m in models]
        picked = self.pick()
        model = picked[1] if picked is not None and picked[1] in offered else (offered[0] if offered else "")
        return {"ok": True, **tiles, "model": model, "models": models, "active": picked[0].label if picked is not None else "", "intro": CARD_INTRO, "profile_line": PROFILE_LINE if settings.profile(self.data_dir)["name"] else "", "size": SIZE_LINE.format(tokens=QUESTION_CHARS // CHARS_PER_TOKEN, chars=QUESTION_CHARS), "message": message, "docker": platform.container_mode()}

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
            return fail(409, "not_signed_in", NOT_SIGNED_IN[name] if name in NOT_SIGNED_IN and self.failed_code(self.providers[name]) in ("no_login", None) and st["why"] != platform.needs_mac_words() else st["why"])     # row 1492 (AP5): a check that is not "not signed in" keeps its own sentence
        return self._turn_on(name)

    def _turn_on(self, name):
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

    @staticmethod
    def failed_code(provider):
        try:
            return provider.failed_check()
        except Exception:  # noqa: BLE001
            return None

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
            self.checked.pop(name, None)             # row 1492: turned off, so its last check no longer stands
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
        saved = settings.ai_read(self.data_dir)
        for name, provider in self.providers.items():
            st = ask.answer_status(provider)             # row 1492 (AP11): ONE status check per provider; the question below uses it
            if not (st["connected"] and self.is_on(name, saved)):
                continue
            started = clock()
            got = ask.ask_provider(Pinned(provider, RECOMMENDED[name], st), ask.Request(text=TEST_QUESTION, question=""))
            took = round(clock() - started, 1)
            answered = isinstance(got, ask.Reply)
            LOG.info("ai: %s tested, %s", name, "answered" if answered else "no answer")
            results.append({"provider": name, "label": provider.label, "answered": answered, "seconds": took,
                            "message": "" if answered else (got.message if isinstance(got, ask.Failure) else TEST_FAILED.format(label=provider.label))})
        if not results:
            return fail(409, "nothing_on", TEST_NOTHING)
        return 200, {"ok": True, "results": results}

    # ----- row 1492: Check again -----
    def progress(self, *_ignored):
        """GET /api/providers/progress: the step each running check is on, so the tile can show the steps with their words. Nothing else."""
        with self.guard:
            return 200, {"ok": True, "steps": dict(self.steps)}

    def cancel(self, body):
        """POST /api/providers/cancel {provider}: ends that provider's running check (and the one request in it). The answer to the check itself says "Cancelled"."""
        name = self.named(body)
        if name is None:
            return fail(400, "bad_request", BAD)
        if name not in self.providers:
            return fail(400, "no_provider", NO_PROVIDER)
        with self.guard:
            event = self.running.get(name)
        if event is not None:
            event.set()
            self.providers[name].stop(self.owner)    # only the check's own request: a question running on it is not ended
        return 200, {"ok": True}

    def reason(self, name, provider, st):
        """(code, the one fixed sentence) for a status that is not signed in. Kinds clark has no sentence for (a version not tested, an odd home folder, a command that is not native) keep their own."""
        label, code = provider.label, self.failed_code(provider)
        if code == "not_found":
            return "not_installed", V_NOT_INSTALLED.format(label=label)
        if code == "api_key" or (code == "no_login" and name == CLAUDE and st["why"].startswith(ask_claude.OTHER_LOGIN)):
            return "wrong_kind", V_WRONG_KIND.format(label=label)
        if code == "no_login":
            return "not_signed_in", V_NOT_SIGNED_IN[name]
        if code == "slow":
            return "slow", V_CHECK_SLOW
        return "not_ready", st["why"]

    def refusal(self, name, provider, got, event):
        """(code, sentence) for a request that was not answered."""
        label = provider.label
        message = got.message if isinstance(got, ask.Failure) else ""
        why = getattr(got, "reason", "")
        if event.is_set() or message == ask.STOPPED:
            return "cancelled", V_CANCELLED.format(label=label)
        if message.startswith(V_BUSY):
            return "busy", V_BUSY
        if isinstance(got, ask_claude.LimitReached) or message.startswith(V_LIMIT[name]):
            return "limit", V_LIMIT[name]
        if why == "expired":
            return "expired", V_EXPIRED.format(label=label)
        if why == "network":
            return "no_network", V_NO_NETWORK.format(label=label)
        if why == "slow" or message in (ask_claude.TOO_SLOW, ai_codex.TOO_SLOW):
            return "slow", V_TOO_SLOW.format(label=label)
        return "no_answer", V_UNKNOWN.format(label=label)

    def step(self, name, step):
        with self.guard:
            self.steps[name] = step

    def check(self, name, provider, event, out):
        """The work of one check, in its own thread so the whole Connect has one deadline: the command, the sign-in, then ONE small request. Fills `out`."""
        command = getattr(getattr(provider, "command", None), "command", None)
        if callable(command):
            self.step(name, "command")
            path, _why = command()
            if path is None:
                out["fail"] = self.reason(name, provider, {"why": _why})
                return
        if event.is_set() or out.get("abandoned"):
            return
        self.step(name, "signin")
        st = ask.answer_status(provider)                 # one status check
        if not st["connected"]:
            out["fail"] = self.reason(name, provider, st)
            return
        if event.is_set() or out.get("abandoned"):
            return
        self.step(name, "ask")
        started = time.monotonic()
        got = ask.ask_provider(Pinned(provider, RECOMMENDED[name], st), ask.Request(text=TEST_QUESTION, question="", cancel=event, owner=self.owner))
        out["seconds"] = round(time.monotonic() - started, 1)
        if isinstance(got, ask.Reply):
            out["answered"] = True
        else:
            out["fail"] = self.refusal(name, provider, got, event)

    def verify(self, body, limit=None):
        """POST /api/providers/verify {provider}: Connected is shown only after ONE real small request was answered with the sign-in (AP1). Turning a provider on is saved only
        after that answer. One deadline for the whole check (AP3). A failure is one fixed sentence (AP4). Nothing of the question or the answer is kept or logged (AP13)."""
        limit = VERIFY_LIMIT if limit is None else limit
        name = self.named(body)
        if name is None:
            return fail(400, "bad_request", BAD)
        if name not in self.providers:
            return fail(400, "no_provider", NO_PROVIDER)
        if platform.container_mode():
            return fail(409, "docker", ask_words.DOCKER)
        provider = self.providers[name]
        with self.guard:
            if name in self.running:
                return fail(409, "busy", V_BUSY)
            event = self.running[name] = threading.Event()
        out, done = {}, threading.Event()

        def work():
            try:
                self.check(name, provider, event, out)
            except Exception:  # noqa: BLE001  nothing of what failed is kept
                out["fail"] = ("no_answer", V_UNKNOWN.format(label=provider.label))
            finally:
                done.set()
        threading.Thread(target=work, daemon=True).start()
        finished = done.wait(limit)
        with self.guard:
            if not finished:
                out["abandoned"] = True
            self.running.pop(name, None)
            self.steps.pop(name, None)
        if not finished:
            provider.stop(self.owner)                    # the check's own request ends (not a question running on it): the check has had its time
            code, words = ("cancelled", V_CANCELLED.format(label=provider.label)) if event.is_set() else ("slow", V_TOO_SLOW.format(label=provider.label))
        elif event.is_set() and "answered" not in out:
            code, words = "cancelled", V_CANCELLED.format(label=provider.label)
        elif "fail" in out:
            code, words = out["fail"]
        else:
            code = None
        if code is not None:
            LOG.info("ai: %s checked, %s", name, code)
            return fail(409, code, words)
        self.checked[name] = {"seconds": out["seconds"], "at": time.strftime("%H:%M")}
        LOG.info("ai: %s checked, answered", name)
        return self._turn_on(name)

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
