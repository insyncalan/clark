# Smoke test result for the Claude provider (#216)

The real-command smoke test (`dev/tools/ask_claude_smoke.py`) run on a Mac against the real `claude` command, version 2.1.312, signed in with a Claude plan, on the tree of commit e79ffeac. The report is copied as printed; the home folder is shown as `~`.

What it shows, in short: with settings on, the planted hooks, apiKeyHelper, settings `env`, CLAUDE.md and MCP server all run (the controls); with the provider's own arguments and environment none of them runs, in the throw-away home and in a project folder under the person's own sign-in, where the run answered. The sign-in check reads no settings file: with settings on, `auth status` reports the planted helper; with the provider's `--setting-sources ""` it does not, and the helper never runs. The settings `env` canary is a note: the project-folder control wrote no temporary file, and the throw-away home's run shows it off. The tool and stop hooks and CLAUDE.md never fire where nobody is signed in, so in the throw-away home they are notes covered by the project-folder run.

Not covered: managed settings an administrator puts on a company Mac, which these flags cannot switch off.

```text
ask clark smoke test: ~/.local/share/claude/versions/2.1.312

NOTE         control, throw-away home with the helper: ran: apiKeyHelper, hook-SessionEnd, hook-SessionStart, hook-UserPromptSubmit, mcp-server, settings-env; ended slow (exit 143)
NOTE         control, throw-away home with no helper and no sign-in: ran: hook-SessionEnd, hook-SessionStart, hook-UserPromptSubmit, mcp-server, settings-env; ended failed (exit 1): 'Not logged in · Please run /login'
NOTE         control, sign-in check with settings on: helper ran: no; reports: api_key_helper
PASS         checks: apiKeyHelper did not run: no marker
NOTE         checks: hook-PreToolUse did not run: not armed by its control here; shown off in the project folder run
PASS         checks: hook-SessionEnd did not run: no marker
PASS         checks: hook-SessionStart did not run: no marker
NOTE         checks: hook-Stop did not run: not armed by its control here; shown off in the project folder run
PASS         checks: hook-UserPromptSubmit did not run: no marker
PASS         checks: mcp-server did not run: no marker
PASS         checks: settings-env did not run: no marker
PASS         the native-program, version and flag checks accept this command: accepted
PASS         sign-in check: the settings file's apiKeyHelper does not run: no marker; with settings on, a question ran it; auth status only reports it
PASS         sign-in check: the settings file's apiKeyHelper cannot change the answer: with settings on it reports api_key_helper; the provider's check reports none
PASS         the sign-in check refuses a home with no Claude sign-in: refused: Claude isn't signed in on this computer. Open Terminal, type claude, and sign in when it asks. Then ask again.
NOTE         isolated, throw-away home: how the run ended: ended failed (exit 1): 'Not logged in · Please run /login'
NOTE         isolated, throw-away home: CLAUDE.md did not run: not armed by its control here; shown off in the project folder run
PASS         isolated, throw-away home: apiKeyHelper did not run: no marker
NOTE         isolated, throw-away home: hook-PreToolUse did not run: not armed by its control here; shown off in the project folder run
PASS         isolated, throw-away home: hook-SessionEnd did not run: no marker
PASS         isolated, throw-away home: hook-SessionStart did not run: no marker
NOTE         isolated, throw-away home: hook-Stop did not run: not armed by its control here; shown off in the project folder run
PASS         isolated, throw-away home: hook-UserPromptSubmit did not run: no marker
PASS         isolated, throw-away home: mcp-server did not run: no marker
PASS         isolated, throw-away home: settings-env did not run: no marker
PASS         isolated, throw-away home: no new file under its ~/.claude: none
PASS         isolated, throw-away home: its ~/.claude.json is byte for byte as it was: unchanged
NOTE         control, project folder: ran: hook-PreToolUse, hook-SessionEnd, hook-SessionStart, hook-Stop, hook-UserPromptSubmit, mcp-server, CLAUDE.md; answered 'SMOKE-CLAUDE-MD-7F3A OK'
NOTE         control, project folder with only the helper: ran: apiKeyHelper; ended slow (exit 143)
NOTE         isolated, project folder: how the run ended: answered 'OK'
PASS         isolated, project folder: CLAUDE.md did not run: no marker
PASS         isolated, project folder: apiKeyHelper did not run: no marker
PASS         isolated, project folder: hook-PreToolUse did not run: no marker
PASS         isolated, project folder: hook-SessionEnd did not run: no marker
PASS         isolated, project folder: hook-SessionStart did not run: no marker
PASS         isolated, project folder: hook-Stop did not run: no marker
PASS         isolated, project folder: hook-UserPromptSubmit did not run: no marker
PASS         isolated, project folder: mcp-server did not run: no marker
NOTE         isolated, project folder: settings-env did not run: not armed by its control, so its silence here shows nothing
PASS         real: the native-program, version, flag and Claude sign-in checks accept this command: Claude is ready. Your question and the parts of the report it needs are sent to Claude, which Anthropic runs.
PASS         real: one question with the person's own sign-in: answered 'OK'
PASS         real: no file for the provider's runs under ~/.claude: none
NOTE         real: other new files under ~/.claude: 2 (another Claude window may have written them; close it and run again to be sure)

RESULT: PASS
```
