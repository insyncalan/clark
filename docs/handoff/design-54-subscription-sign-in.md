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
3. **ChatGPT (#52).** `ai_codex.py` behind the same interface, on the card with Claude. Slices 2 and 3 are one PR (619), which replaced 589.

## Decisions in slice 1

- **Per-model limit** is the size of what is sent (#53, question 6), not a count of sends. An earlier draft counted sends with placeholder numbers; that would have blocked people with limits nobody chose, so it is gone. Claude's models all have a 1M token context today, and clark's own `ask.MAX_REQUEST` (70,000 characters) is far below the limit, so the check does not bind yet. It is there for the smaller ChatGPT models and for any later rise in clark's own cap.
- **A limit** is read from the command's output. The shapes are written from what the command is known to do, not recorded: nobody has seen a real one (accepted, #53, question 7).
- **An alias the command refuses** was tested on the real command on 04-11-2026: `is_error` true, status 404, "There's an issue with the selected model".

## Decisions in slice 2

- **Connect and Disconnect are about clark's use of the command, never the sign-in.** clark can't sign a person in, and signing them out would break their other work. Disconnect only stops clark using it, and says so. A person already signed in counts as connected, as before.
- **Sonnet is the default model**, sent as `--model sonnet` (the owner, 04-11-2026: "default for claude is always sonnet"). Before this, the command chose. On a command too old to choose a model, the default is dropped and the command's own is used; a model the person chose gets the plain line.
- **Haiku asks first**, and a yes is remembered. Opus and Fable are simply offered.
- **ChatGPT is off until the person connects it:** what they ask would go to a second company. The model chosen decides the provider, and clark never moves to another provider by itself.
- **Every line saying where a question goes follows the provider in use** (`askWords.named`), because it has to be true.
- **The suggestions menu stays off:** the launcher still passes no `ai=`, so the line under the card still says suggestions come later.

## The ChatGPT run (slice 3), from the tests on #52

`codex exec` in its read-only sandbox **can read any file** and send it to OpenAI. So a run needs both of these, and either alone is not enough:

1. Every tool feature off.
2. An outer macOS sandbox that clark writes: an allow-list of what may be read, covering Codex itself, its sign-in and an empty working folder. Writes only to Codex's own folder and that working folder.

**Why `(allow default)` is acceptable:** it leaves system files readable (/etc, /Library, /Applications). Those are not the person's data, and Codex can't start without many of them. The wall is for the person's files and secrets, and it denies their home folder by name wherever it is. A home that isn't a real folder, or sits outside /Users and /private/var/folders, refuses the run.

**What the wall doesn't do:** it stops file reads and writes, not the network. A macOS sandbox rule names an address or a port, never a host name, so it can't limit Codex to OpenAI. So the tools-off list stops the rest, and the Codex version is pinned to the tested range: a newer Codex could bring a tool the list doesn't name, so it's refused ("This version of Codex has not been tested with clark: update clark."). A new version means a new release of clark, and a new run of the checks below.

**The hand run still to record on #52:** a real run with planted files in the home and temp folders (neither read), and a request to read ~/.ssh giving no content; Codex answering under the wall; `sandbox-exec` missing makes the run refuse; Stop leaves no stray process.

Also: the native binary, not the npm script; an environment built from nothing, as `ask_claude.child_env` does; `--ignore-user-config`, `--ignore-rules`, `--ephemeral`. A test must plant a file and fail if the run can read it. clark's rules replace Codex's own prompt. The owner confirms the plan's terms allow this. Still open: the limit shape, and other ways of installing Codex.

## Visible words for the owner to rule on

- "That model isn't one clark can use. Nothing was sent."
- "This version of Claude can't choose a model. Update Claude to choose one."
- "Claude says that model can't be used with this sign-in. Choose another model in Settings."
- "Claude says the limit for this model has been reached, so nothing more was sent. You could ask again with Sonnet, Haiku, Fable. clark doesn't switch unless you choose to."
- "That is too much text for Opus, so nothing was sent. Ask about less, or choose another model in Settings."

Slice 2 adds:

- "Connect Claude for ask clark: the passages it sends leave this computer, go to Claude and count against your Claude plan. No password or key is kept."
- "Through your Claude subscription, using the Claude command on this computer."
- "Through your ChatGPT subscription, using the Codex command on this computer. What you ask goes to OpenAI." (the ChatGPT tile; it replaced "Coming soon, through your ChatGPT sign-in." when ChatGPT went live in PR 619, #52)
- "Connected. Asking will use Claude Sonnet." and "Asking will use Claude Sonnet." (the model name changes)
- "Disconnected. You're still signed in to Claude on this computer, but clark won't use it."
- "Claude Haiku is smaller than the recommended model, so its answers may be less careful. Use it anyway?" with "Use it anyway" and "Keep the model I have"
- "Claude isn't connected in Settings. Connect it there to use this."
- "Could not check the AI connection just now. Reload the page to try again."
- Refusals: "That could not be read. Reload the page and try again.", "That isn't something clark can connect yet.", "Connect Claude first.", "Your settings couldn't be read, so the AI choice was not changed."
- Labels: "Model for ask clark", "(recommended)", "Connected", "Not connected", "Later", "Connect", "Disconnect", "OpenAI"

All of these reach a screen with slice 2. The owner approved the whole list on 04-11-2026 ("Approve all of it"), with the two wall sentences. A new sentence still goes through the Head.
