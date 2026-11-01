"""ai: the logic of POST /api/ai/suggest, GET /api/ai/status and POST /api/ai/stop (#72, slice 4). Unguarded; server.py only
routes to it.

ONE RUN PATH. This does not start a model of its own. It borrows the ask service (ask_service.AskService): the same provider (the
one the Claude command module fills), the same switch and the same Stop. So a suggestion and a question share one run at a time:
the provider's own lock refuses a second run, and this service looks at it first so the person gets a plain line, not a fault.

THE SWITCH. There is one switch for Claude on this computer, the one in Settings under Asking. AI suggestions are off while it is off.

ONE-SHOT AND STATELESS. A request is {option, place, text, instruction}. It is checked and turned into the prompt by ai_menu
(build_prompt: hidden characters, size, the option and place), sent through the provider with no tools, and the reply is checked by
ai_menu.check_reply and turned into cleaned HTML. The answer is the html, the notes and the word by word changes, or one plain
line. Nothing is kept: the card lives on the page, and nothing is applied here.

WHAT LEAVES: only the prompt ai_menu builds from the text, the option's fixed task and the one-line instruction. No project, ID,
person or tool is given. The log holds the option, the place and the length, never the text.

Every answer is (status, {ok, ...}); a refusal has a stable `code` and a plain `message` with no fault text, path or key.
"""
import logging
import threading

from clark import ai_menu, ask, ask_claude, secret_screen

LOG = logging.getLogger("clark.ai")
FIELDS = {"option", "place", "text", "instruction"}
PROVIDER_LABEL = "Claude"
# The provider's own plain lines that ask clark shows as they are (a timeout, a sign-out, busy): the same lines here, each with its
# own code. Any other provider line is not shown (its words could hold the request or a path); that is the generic "failed".
PROVIDER_LINES = {ask_claude.TOO_SLOW: "timeout", ask_claude.NOT_SIGNED_IN: "not_signed_in",
                  ask_claude.API_KEY_LOGIN: "not_signed_in", ask_claude.OTHER_LOGIN: "not_signed_in", ask_claude.BUSY: "busy",
                  ask.STOPPED: "stopped"}
OPS = {"=": "same", "-": "del", "+": "add"}
MESSAGES = {
    "bad_request": "That request could not be read. Nothing was sent. Reload the page and try again.",
    "secret": ask.SECRET,
    "off": ai_menu.why_off("off"),
    "not_signed_in": ai_menu.why_off("not_signed_in", PROVIDER_LABEL),
    "busy": ai_menu.why_off("busy"),
    "failed": ai_menu.FAULT_MESSAGES["default"],
    "stopped": ai_menu.FAULT_MESSAGES["stopped"],
    "timeout": ask_claude.TOO_SLOW,
    "not_running": "No suggestion is being made just now.",
    "stopping": "Stopping.",
    "ready": "AI suggestions are on. The text you select and your instruction go to Claude, which Anthropic runs.",
}


class AiService:
    """`ask_service` is the AskService whose provider, switch and Stop this uses."""

    def __init__(self, ask_service):
        self.ask_service = ask_service
        self.run_lock = threading.Lock()           # this service's own run; the provider's lock covers a question's run
        self.guard = threading.Lock()              # #284: the run is registered, and Stop looks at it, only under this
        self.stopped = threading.Event()           # set by Stop for the run now going; cleared only as a run is registered
        self.owner = object()                      # this service's token: Stop ends the provider's run only if it is ours

    def fail(self, code, message=None):
        return {"ok": False, "code": code, "message": message or MESSAGES[code]}

    @property
    def provider(self):
        return self.ask_service.provider

    def busy(self):
        lock = getattr(self.provider, "lock", None)
        return self.run_lock.locked() or bool(callable(getattr(lock, "locked", None)) and lock.locked())

    def state(self):
        """One of ai_menu.STATES, in the order a refusal is made: off, then not signed in, then busy."""
        if not self.ask_service.enabled():
            return "off"
        if not ask.answer_status(self.provider)["connected"]:
            return "not_signed_in"
        return "busy" if self.busy() else "ready"

    # ----- GET /api/ai/status -----
    def status(self, *_ignored):
        state = self.state()
        return 200, {"ok": True, "on": state != "off", "signed_in": state in ("ready", "busy"), "busy": state == "busy",
                     "state": state, "provider": PROVIDER_LABEL, "line": MESSAGES[state]}

    # ----- POST /api/ai/stop -----
    def stop(self, body=None):
        if body not in (None, {}):
            return 400, self.fail("bad_request")
        with self.guard:
            running = self.run_lock.locked()       # only a suggestion's own run is stopped from here, never a question's
            if running:
                self.stopped.set()                 # seen by the provider as it registers (request.cancel), if it has not yet
        if running:
            stop = getattr(self.provider, "stop", None)
            if callable(stop):
                stop(owner=self.owner)             # and, if it has registered, ended there; never another service's run
        return 200, {"ok": True, "stopped": running, "message": MESSAGES["stopping" if running else "not_running"]}

    # ----- POST /api/ai/suggest -----
    @staticmethod
    def checked_option(option):
        """The option as ai_menu knows it, else a fixed word: what the log may hold (never the unchecked text of the request)."""
        return option if option in ai_menu.OPTIONS else "unknown"

    @staticmethod
    def read_body(body):
        """(option, place, text, instruction) or None for a body of the wrong shape."""
        if not isinstance(body, dict) or not {"option", "place", "text"} <= set(body) or not set(body) <= FIELDS:
            return None
        got = tuple(body.get(k, "") for k in ("option", "place", "text", "instruction"))
        return got if all(isinstance(v, str) for v in got) and got[1] in ai_menu.PLACES else None

    def suggest(self, body):
        got = self.read_body(body)
        if got is None:
            return 400, self.fail("bad_request")
        option, place, text, instruction = got
        # A password or key in the text or in Ask... is refused as it was given, before any cleaning or squeezing (screen
        # before the line breaks are joined), before the run lock and before the provider. Nothing is echoed or logged but the shape.
        if secret_screen.looks_like_secret(text) or secret_screen.looks_like_secret(instruction):
            LOG.info("ai suggest refused: secret option=%s place=%s length=%d", self.checked_option(option), place, len(text))
            return 400, self.fail("secret")
        state = self.state()
        if state != "ready":
            return 409, self.fail(state)
        try:
            req = ai_menu.build_prompt(option, text, place, instruction)
        except ai_menu.Refused as e:
            return 400, self.fail("refused", str(e))
        with self.guard:                             # #284: registered and cleared together, so a Stop is never lost or wiped
            if not self.run_lock.acquire(blocking=False):
                return 409, self.fail("busy")
            self.stopped.clear()
        try:
            if not self.ask_service.enabled():       # the switch again, just before anything leaves
                return 409, self.fail("off")
            LOG.info("ai suggest option=%s place=%s length=%d", req["option"], req["place"], len(text))
            try:
                reply = self.provider.ask(ask.Request(text=req["prompt"], question="", owner=self.owner, cancel=self.stopped))
            except Exception:  # noqa: BLE001  a provider fault is one plain line; its text could hold the request
                reply = ask.Failure(MESSAGES["failed"])
            if self.stopped.is_set():
                return 200, self.fail("stopped")
            if isinstance(reply, ask.Failure):       # a plain line of the provider's own is shown as ask clark shows it
                code = PROVIDER_LINES.get(reply.message)
                return 200, self.fail(code or "failed", reply.message if code else None)
        finally:
            self.run_lock.release()
        if not isinstance(reply, str):
            return 200, self.fail("failed")
        checked = ai_menu.check_reply(reply, req["original"], req["option"], req["place"])
        if not checked["ok"]:
            return 200, self.fail("failed", checked["message"])
        try:
            html = ai_menu.to_html(checked["text"])
        except Exception:  # noqa: BLE001  text that cannot be cleaned is not shown
            return 200, self.fail("failed", "The suggestion couldn't be used. Try again.")
        changes = [{"op": OPS[k], "text": t} for k, t in ai_menu.word_diff(req["original"], checked["text"])]
        return 200, {"ok": True, "html": html, "notes": checked["notes"], "changes": changes}
