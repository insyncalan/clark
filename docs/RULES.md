# Rules for clark

Every session working here follows these. They were agreed with the owner on 27-10-2026.

## What this project is

The owner's side project. It is separate from creaite: its own repo, its own board (to be set up), its own releases. It reuses creaite's code as a base, so changes here never go back into creaite without the owner's explicit word.

## Non-negotiables

- **Private, always** ("Keep clark private"). Making the repo public, pushing to another repo or sharing outside the team needs the owner's word.
- **No real names or client data.** Use fictional demo data in code, tests, docs and examples. Never copy a real client, company or person's name from the owner's vaults or from creaite's private repos.
- **A real client brand stays on this laptop.** Logos, colours, fonts, names and source files of a real client brand live only in `system/branding/`, which git ignores. Nothing derived from them that names or shows the client is committed. The repo, its tests and examples use a fictional demo brand.
- **No secrets.** No tokens, keys or passwords in the repo, ever. Credentials stay in the keychain or environment.
- **The owner decides scope.** The team proposes; the owner chooses what is built and when.
- **Releases publish without the owner's sign-off** ("You do not need my eyes to publish"): the Head publishes a private release once the gate is green on the exact commit and the required verdicts are in. Public posts still wait for the owner.
- **Money goes to the owner first** ("alert me before I have to spend money"): anything that would cost money, such as paid Actions minutes, a plan or a service, is raised with him before it happens.
- **Every change has a way back.** Work on branches, merge by pull request, keep history. No force-push, no history rewriting, no tags without the owner's word.
- **British English, short outputs, answer first.** The owner reads headlines; detail on request.
- **Dates:** DD-MM-YYYY when shown to a person, YYYY-MM-DD when stored, in file names and in data.
- **The product's name and wording:** decided with the owner and recorded in `DECISIONS.md`. Until then, follow creaite's plain-words rules for anything a user reads (no internal jargon) and never start a line of user text with a product name in lower case where the name is lower case.
- **Tests:** everything that can be a test is a test; a hand check holds only judgement or live-only steps. The reviewer is never the builder.

## Reusing creaite's code

- Copy what is needed, with the source path and commit noted in the reuse record.
- Do not edit creaite's repos from here. If a change belongs in creaite, raise it with the Head.
- creaite's guarded files (tracker, filechange, reach, permissions, backup, update, live_server, client_leak, edit_ai, draft_delivery) carry creaite's approval rules. Copies in this repo are ordinary code here, but any copy of them is marked in the reuse list and reviewed by a second reader before use.
- **Who reviews a copy of a guarded file here:** teammates are not on this project, so a second reader is whoever the owner names; until he names one, the Head reads it (from creaite) before it is used. The owner approves the exact copy in his own words.
- Check privacy: nothing from creaite's private repos (a private repo, the team repo) is copied here.

## Working with the owner

- The owner's replies come as "AM: ..." lines; act on exactly what they say.
- Questions that block work go to the owner in one short message, with a recommendation.
