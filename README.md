# clark

clark is a report editor for programme managers. It keeps a project's work items, milestones and use cases in a local database with history and undo, imports and exports them as Excel, and publishes a weekly report as a single self-contained HTML page. It runs on your own computer, and nothing leaves it unless you publish a report.

**Status: early development (version 0.1 in progress).** This repository is a published copy of a private development repository: each publish adds one snapshot of the code, tests and design notes, with none of the private history. All data in it is fictional demo data. It has **no licence yet**, which means all rights are reserved until one is added.

## Try it

To look around with made-up projects, run `python3 -m clark --demo`.

## Run the tests

```
python3 dev/run_tests.py
```

## Where to read more

- `docs/PROJECT-BRIEF.md`: what clark is for.
- `docs/ARCHITECTURE.md` and `docs/handoff/`: how it is built and why.
- `docs/RULES.md`: the rules the project follows (no real names or client data, plain words, British English).
- the reuse record: the code it builds on, with where each part comes from.
