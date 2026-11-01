# Claude Code settings example

`dev/claude-settings.example.json` is a shared permissions baseline for working on this repo.

- Read-only `gh` commands and PR/issue writes are allowed; pushes to main, force pushes, tags, branch deletion, releases, secrets and identity changes are denied.
- Install: copy it to `~/.claude/settings.json`, or merge its `permissions.allow` and `permissions.deny` arrays into your existing file.
- It is an example to copy. Claude Code does not read it from here automatically.
- The repo's `.claude/` folder stays private and is never committed.
- `gh api` is not allowed: GET-only cannot be expressed in this format.
