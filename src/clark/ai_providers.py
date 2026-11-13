"""AI providers for ask clark (#54, the subscription routes). A provider is a small object: `name`, `models()` (the fixed aliases it
accepts), `status()`, `ask(request, model=None)` and `others(model)` (what to offer when a limit is reached). There is no key here, no
keychain and no network call: the Claude provider is the person's own `claude` command, run by ask_claude.ClaudeCommand (the one place
that starts it, through platform.py). The API-key route is a later item (#643). `ai_codex.py` is the ChatGPT command.

The size of what is sent is limited per model, pinned in code from each model's context, so a change is a reviewed change. A limit never
switches model by itself: the answer is a `LimitReached` that names the other models, and the person chooses.
"""
import threading

from clark import ai_codex, ask, ask_claude

# Each model's context window in tokens (the owner's answer on #53, question 6). Characters allowed are half of it: a token is often
# more than two characters of English, but text in other scripts can be fewer, and the provider's own prompt and the reply need room.
CONTEXT_TOKENS = {"opus": 1000000, "sonnet": 1000000, "haiku": 1000000, "fable": 1000000}
CHARS_PER_TOKEN = 0.5
TOO_BIG = "That is too much text for {model}, so nothing was sent. Ask about less, or choose another model in Settings."


def most_chars(model):
    """The longest request text a Claude `model` may be sent (Subscription.most_chars for any provider)."""
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


class Subscription(Provider):
    """A person's own signed-in command as a provider. `command` is a seam for the tests."""
    contexts = {}
    names = {}

    def __init__(self, command):
        self.command = command
        self.name = command.provider

    def models(self):
        return self.command.models

    def status(self):
        return self.command.status()

    def failed_check(self):
        """The short code of the check that last failed (ask_claude.ClaudeCommand.failed), or None."""
        return getattr(self.command, "failed", None)

    def most_chars(self, model):
        """The longest request text `model` may be sent. No model chosen: the smallest, because the command's own choice isn't known here."""
        tokens = self.contexts[model] if model is not None else min(self.contexts.values())
        return int(tokens * CHARS_PER_TOKEN)

    def ask(self, request, model=None, prefer=False):
        if model is not None and not (isinstance(model, str) and model in self.models()):
            return ask.Failure(ask_claude.MODEL_REFUSED)
        if len(request.text) > self.most_chars(model):
            return ask.Failure(TOO_BIG.format(model=self.names.get(model, "this model")))
        return self.command.ask(request, model, prefer=prefer) if prefer else self.command.ask(request, model)

    def stop(self, owner=None):
        return self.command.stop(owner)


class ClaudeSubscription(Subscription):
    """The Claude command, signed in with the person's own Claude plan."""
    contexts = CONTEXT_TOKENS
    names = ask_claude.MODEL_NAMES
    label, company = "Claude", "Anthropic"

    def __init__(self, command=None):
        super().__init__(command if command is not None else ask_claude.ClaudeCommand())


class ChatGPTSubscription(Subscription):
    """The Codex command, signed in with the person's own ChatGPT plan. The three layers around a run are in ai_codex.py."""
    contexts = ai_codex.CONTEXT_TOKENS
    names = ai_codex.MODEL_NAMES
    label, company = "ChatGPT", "OpenAI"

    def __init__(self, command=None):
        super().__init__(command if command is not None else ai_codex.CodexCommand())


class Chosen(ask.Provider):
    """What ask clark and the suggestions are given: the provider and model chosen in Settings › AI. `pick` is read for every question, so a change
    in Settings counts at once: it gives (provider, model, prefer), or None when nothing is connected. `prefer` means the model is only a default, so
    an older command that can't choose a model still answers; a model the person chose is used or refused. It never moves to another provider by
    itself: a limit or a fault is told, and the person chooses. While nothing is connected nothing is asked and the status says why."""
    name = "chosen"

    def __init__(self, providers, pick, off_words):
        self.providers, self.pick, self.off_words = tuple(providers), pick, off_words
        self.lock = threading.Lock()       # one run at a time across providers, even if the person switches while a question runs (ai_service.busy reads it)
        for provider in self.providers:
            provider.command.lock = self.lock

    def _active(self):
        return self.pick() or (None, None, False)

    @property
    def label(self):
        provider = self._active()[0]
        return provider.label if provider is not None else ""

    def status(self):
        provider = self._active()[0]
        return provider.status() if provider is not None else {"connected": False, "why": self.off_words}

    def ask(self, request):
        provider, model, prefer = self._active()
        if provider is None:
            return ask.Failure(self.off_words)
        return provider.ask(request, model, prefer=prefer)

    def stop(self, owner=None):
        return any([p.stop(owner) for p in self.providers])     # every one: a run may have started before the choice changed


def provider_for(name, **seams):
    """The provider called `name`, or None."""
    kinds = {ask_claude.PROVIDER: ClaudeSubscription, ai_codex.PROVIDER: ChatGPTSubscription}
    return kinds[name](**seams) if name in kinds else None
