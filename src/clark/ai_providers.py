"""AI providers for ask clark (#54, the subscription routes). A provider is a small object: `name`, `models()` (the fixed aliases it
accepts), `status()`, `ask(request, model=None)` and `others(model)` (what to offer when a limit is reached). There is no key here, no
keychain and no network call: the Claude provider is the person's own `claude` command, run by ask_claude.ClaudeCommand (the one place
that starts it, through platform.py). The API-key route is a later item (#643).

The size of what is sent is limited per model, pinned in code from each model's context, so a change is a reviewed change. A limit never
switches model by itself: the answer is a `LimitReached` that names the other models, and the person chooses.
"""
from clark import ask, ask_claude

# Each model's context window in tokens (the owner's answer on #53, question 6). Characters allowed are half of it: a token is often
# more than two characters of English, but text in other scripts can be fewer, and the provider's own prompt and the reply need room.
CONTEXT_TOKENS = {"opus": 1000000, "sonnet": 1000000, "haiku": 1000000, "fable": 1000000}
CHARS_PER_TOKEN = 0.5
TOO_BIG = "That is too much text for {model}, so nothing was sent. Ask about less, or choose another model in Settings."


def most_chars(model):
    """The longest request text `model` may be sent. No model chosen: the smallest, because the command's own choice isn't known here."""
    tokens = CONTEXT_TOKENS[model] if model is not None else min(CONTEXT_TOKENS.values())
    return int(tokens * CHARS_PER_TOKEN)


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

    def __init__(self, command=None):
        self.command = command if command is not None else ask_claude.ClaudeCommand()

    def models(self):
        return ask_claude.MODELS

    def status(self):
        return self.command.status()

    def ask(self, request, model=None):
        if model is not None and not (isinstance(model, str) and model in self.models()):
            return ask.Failure(ask_claude.MODEL_REFUSED)
        if len(request.text) > most_chars(model):
            return ask.Failure(TOO_BIG.format(model=ask_claude.MODEL_NAMES.get(model, "this model")))
        return self.command.ask(request, model)

    def stop(self, owner=None):
        return self.command.stop(owner)


class Chosen(ask.Provider):
    """What ask clark and the suggestions are given: `provider` with the choice in Settings › AI applied. `on` and `model` are read for
    every question, so a change in Settings counts at once. While it is off nothing is asked and the status says why."""

    def __init__(self, provider, on, model, off_words):
        self.provider, self.on, self.model, self.off_words = provider, on, model, off_words
        self.name = provider.name

    @property
    def lock(self):
        return self.provider.command.lock       # one run at a time, shared with a question's run (ai_service.busy reads it)

    def status(self):
        return self.provider.status() if self.on() else {"connected": False, "why": self.off_words}

    def ask(self, request, model=None):
        if not self.on():
            return ask.Failure(self.off_words)
        return self.provider.ask(request, self.model() if model is None else model)

    def stop(self, owner=None):
        return self.provider.stop(owner)


def provider_for(name, **seams):
    """The provider called `name`, or None."""
    return ClaudeSubscription(**seams) if name == ask_claude.PROVIDER else None
