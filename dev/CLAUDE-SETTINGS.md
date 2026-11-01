# Claude Code settings example

`dev/claude-settings.example.json` is an example permissions baseline for working on this repo.

- Prefix rules are a guardrail only: wrappers (`bash -c`, `env`, `xargs`, `git -C x push`) and compound commands get past them. Branch protection on main ("protect main", requiring "Tests passed") is the real control. The matcher syntax is a reading of the docs and is untested against the real tool.
- Install: copy it to `~/.claude/settings.json`, or merge its `permissions.allow` and `permissions.deny` arrays into your existing file. Claude Code does not read it from here automatically.
- The repo's `.claude/` folder stays private and is never committed.
- Not expressible: GET-only `gh api` (not allowed at all; write flags denied), `gh -R x ...` forms (not matched), and a bare `git config user.name` deny (a read cannot be told from a write, so it is dropped; only flagged forms are denied).
