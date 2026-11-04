# #54: AI sign-in through subscriptions (v0.11)

Replaces the API-key plan in `readiness-54-providers.md`. The owner's answers are on items #53 and #54. The Codex test results are on #52.

## Scope

- Claude through the person's `claude` command, and ChatGPT through the person's `codex` command. No key is stored, and clark makes no network call of its own.
- The API-key route is #643, later. So there is no keychain code, no HTTPS caller and no key id in this release.
- OpenAI may be used on any project: no per-project mark (owner, 04-11-2026).
- Windows is v1.1.

## Slices, one pull request each

1. **Claude models and limits (this one).** `--model` from a fixed alias list, a plain line when the command refuses an alias, a limit result that offers other models and never switches, and a size limit per model. `ai_providers.py` is new and nothing calls it yet.
2. **Wiring and the card (#446, #617).** The chosen provider and model in settings (no secrets), ask clark and suggestions going through `ai_providers`, `ai_menu.ask_request` taking its production caller, and the Settings AI card from the prototype.
3. **ChatGPT (#52).** `ask_codex.py` behind the same interface.

## Decisions in slice 1

- **Per-model limit** is the size of what is sent (#53, question 6), not a count of sends. An earlier draft counted sends with placeholder numbers; that would have blocked people with limits nobody chose, so it is gone. Claude's models all have a 1M token context today, and clark's own `ask.MAX_REQUEST` (70,000 characters) is far below the limit, so the check does not bind yet. It is there for the smaller ChatGPT models and for any later rise in clark's own cap.
- **A limit** is read from the command's output. The shapes are written from what the command is known to do, not recorded: nobody has seen a real one (accepted, #53, question 7).
- **An alias the command refuses** was tested on the real command on 04-11-2026: `is_error` true, status 404, "There's an issue with the selected model".

## Decisions in slice 2

- **Connect and Disconnect are about clark's use of the command, never the sign-in.** clark can't sign a person in, and signing them out would break their other work. Disconnect only stops clark using it, and says so. A person already signed in counts as connected, as before.
- **Opus is the default model**, sent as `--model opus` (FR-65: the recommended model is the default). Before this, the command chose. A plan without it gets the plain line and can pick another.
- **Sonnet and Haiku ask first**, and a yes is remembered. Fable is simply offered.
- **The OpenAI tile says Later** until slice 3.
- **The AI menu stays off:** the launcher still passes no `ai=`, so the line under the card still says suggestions come later.

## The ChatGPT run (slice 3), from the tests on #52

`codex exec` in its read-only sandbox **can read any file** and send it to OpenAI. So a run needs both of these, and either alone is not enough:

1. Every tool feature off.
2. An outer macOS sandbox that clark writes: an allow-list of what may be read, covering Codex itself, its sign-in and an empty working folder. Writes only to Codex's own folder and that working folder.

Also: the native binary, not the npm script; an environment built from nothing, as `ask_claude.child_env` does; `--ignore-user-config`, `--ignore-rules`, `--ephemeral`. A test must plant a file and fail if the run can read it. Still open: the limit shape, whether clark's rules can replace Codex's own prompt, other ways of installing Codex, the plan's terms.

## Visible words for the owner to rule on

- "That model isn't one clark can use. Nothing was sent."
- "Claude says that model can't be used with this sign-in. Choose another model in Settings."
- "Claude says the limit for this model has been reached, so nothing more was sent. You could ask again with Sonnet, Haiku, Fable. clark doesn't switch unless you choose to."
- "That is too much text for Opus, so nothing was sent. Ask about less, or choose another model in Settings."

Slice 2 adds:

- "Sign in to Claude for ask clark and the AI menu: the passages they send go to Claude. No password or key is kept."
- "Through your Claude subscription, using the Claude command on this computer."
- "Coming soon, through your ChatGPT sign-in."
- "Connected. Asking will use Claude Opus."
- "Disconnected. You're still signed in to Claude on this computer, but clark won't use it."
- "Asking will use Claude Sonnet."
- "Claude Haiku is smaller than the recommended model, so its answers may be less careful. Use it anyway?" with "Use it anyway" and "Keep the model I have"
- "Claude isn't connected in Settings. Connect it there to use this."
- "Could not check the AI connection just now. Reload the page to try again."

The first four lines above reach a screen with slice 2.
