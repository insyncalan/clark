"""AI providers for ask clark (item 54, slice 3: the Claude subscription route only).

A provider is a small object: `name`, `models()` (the fixed aliases it accepts), `status()`, `ask(request, model=None)` and
`others(model)` (what to offer when a limit is reached). There is no key here, no keychain and no network call: the Claude
provider is the person's own `claude` command, run by ask_claude.ClaudeCommand (which is the one place that starts it, through
platform.py). This is the one module a later provider that does reach the network will be added to (a static test keeps every
other module free of network and subprocess imports).

A limit never switches model by itself: the answer is a `LimitReached` that names the other models, and the person chooses.
"""
import threading
import time

from clark import ask, ask_claude

# The most sends per model in one window, counted by clark before it asks the command, so a model that is used up is not tried
# again. PINNED IN CODE, so a change is a reviewed change. Numbers: owner to confirm (placeholders, item 54).
SEND_WINDOW = 5 * 3600.0
SEND_LIMITS = {"opus": 20, "sonnet": 60, "haiku": 120, "fable": 10}


class Provider:
    """The interface every provider keeps."""
    name = ""

    def models(self):
        return ()

    def status(self):
        return {"connected": False, "why": ask.NOT_READY}

    def ask(self, request, model=None):
        raise NotImplementedError

    def others(self, model):
        return tuple(m for m in self.models() if m != model)


class ClaudeSubscription(Provider):
    """The Claude command, signed in with the person's own Claude plan. `command` is a seam for the tests."""
    name = ask_claude.PROVIDER

    def __init__(self, command=None, limits=None, window=SEND_WINDOW, clock=time.monotonic):
        self.command = command if command is not None else ask_claude.ClaudeCommand()
        self.limits = dict(SEND_LIMITS if limits is None else limits)
        self.window, self.clock = window, clock
        self.sent = {}                        # model -> times of the sends still inside the window
        self.lock = threading.Lock()

    def models(self):
        return ask_claude.MODELS

    def status(self):
        return self.command.status()

    def _spent(self, model):
        """True when `model` has used its sends for this window. Otherwise this send is counted."""
        if model is None:
            return False                      # the command's own choice: its limit event decides
        now = self.clock()
        with self.lock:
            recent = [t for t in self.sent.get(model, ()) if now - t < self.window]
            if len(recent) >= self.limits.get(model, 0):
                self.sent[model] = recent
                return True
            self.sent[model] = recent + [now]
            return False

    def ask(self, request, model=None):
        if model is not None and not (isinstance(model, str) and model in self.models()):
            return ask.Failure(ask_claude.MODEL_REFUSED)
        if self._spent(model):
            return ask_claude.limit_failure(model)
        return self.command.ask(request, model)

    def stop(self, owner=None):
        return self.command.stop(owner)


def provider_for(name, **seams):
    """The provider called `name`, or None. Only the Claude subscription exists in this slice."""
    return ClaudeSubscription(**seams) if name == ask_claude.PROVIDER else None
