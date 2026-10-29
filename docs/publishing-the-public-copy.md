# Publishing the public copy

clark's development stays in a private repo (the tool reads its address from this checkout's `origin` when it runs; it is not written in the tool). What the world sees is a **clean public copy**: a snapshot of the files at one commit, pushed as one new commit by a neutral author called "clark". No history, no real names, no internal notes. `dev/tools/publish_public.py` does it, and refuses to push unless every check passes.

Nothing is ever published without the owner's word (RULES.md). The tool never force-pushes, never makes a tag, never deletes, and never writes to your git settings.

## What is published, and what is not

Everything git tracks at the commit you name, read from git's own objects. Files that are only on this laptop (anything ignored or not committed, such as `system/branding/` and `comms/`) can never be in it.

These internal working notes are taken out of the snapshot (the list is `EXCLUDED` in the script, pinned by a test):

- `dev/HEAD-LOG.md`
- `docs/DECISIONS.md`
- the two hand-over notes between the project's leads (their file names hold a person's name, so the names are not written out here; both are in `EXCLUDED`)
- `docs/TEAM-AND-ROLES.md` (internal staffing, and it names a private repository)
- `.claude/`
- `comms/`
- `system/branding/`

The notes files are expected in the private repo and are removed quietly. `comms/` and `system/branding/` are different: they are meant to stay out of git altogether (`.gitignore`). If a file under either is tracked at the commit, someone force-added it, so the tool refuses (it shows only the file's place number) instead of removing it quietly. Find out why in the private repo, take the file out of git by a normal change, and run again.

`docs/handoff/` is published: the tests read it, and it holds technical design notes with no names.

## The public README

The private `README.md` is never published. The snapshot's `README.md` is the file `docs/public/README.md` of the private repo, byte for byte, and `docs/public/` itself is then left out of the snapshot (it is only the source of that README). If a commit has no `docs/public/README.md`, the tool refuses and says so. Change the public text there, by a normal change.

## The scrub

The private repo keeps its attributions and is never edited by the tool. In the snapshot only, between reading a file from git and writing it, `scrub(path, data)` in the script rewrites the same bytes the same way every time. The listed words are people's names, the names of private repos and boards, a hosting detail, and the name of the reuse record. They are kept ROT13 in the script (which is published too), so the script does not carry them either.

- **Attributions** such as "(the owner, 28-10-2026, relayed by a teammate: "...")" lose the attribution and keep the words quoted.
- **The reuse record** (the reuse record's name, written as a link or in backticks) becomes "the reuse record", and a relative link to a file that is not in the snapshot becomes its text, so nothing dangles. The record itself stays in the copy, because tests read it.
- **The hosting detail** becomes "a Linux machine" (or "a Linux host").
- **In `.md` and `.txt`**, people left in a sentence become roles: the owner, the Head, the project lead, otherwise "a teammate"; private repos become "the team repo", "the planning repo" or "a private repo"; a file name that holds a person's name becomes "an internal note".
- **In code files** only comments and docstrings are touched, never code: Python (read with `tokenize` and `ast`), JavaScript, CSS, SQL, YAML, HTML and SVG, and the dotfiles `.gitignore` and `.gitattributes`. A comment or docstring line that still names a listed word is **dropped**, not reworded; the rest of the line (the code before a trailing comment) is kept, and a docstring keeps its quotes, so the file stays valid. "Internal only" is dropped from comments in `tests/` and `.sql` files only (it is a real label in the product and in `src/` notes).
- **Anything else** (JSON, images, zips, Office files, a file that is not UTF-8) is not changed; the guard decides.
- **Team branches and lower-case pairs.** A branch name such as `team-<first name>-31-store` (also `origin/...`) keeps its shape with a plain word (`team-a-31-store`); a parenthesised quote that names two team members in lower case is dropped. Elsewhere (code, JSON) the guard refuses both.
- **Reads well.** "Team" before a name goes with the name (it becomes the name's role); a list of the same role or private repo is said once ("teammates"); a private repo's name with a path inside it is one phrase, also in a comment, so no sentence is cut.
- Bare issue numbers such as `#31` are not changed: they name no private repo.

A listed word in **code** (an identifier, a string, test data) cannot be dropped, so it fails the guard (next). Fix it in the private repo with a neutral change: rename the identifier, or take the name out of the label.

## The guard

After the scrub, check 6 searches every published path, file and part of a zip (nested up to four levels, part names too) for a listed word, ignoring letter case, every invisible or format character (zero-width, soft hyphen, direction marks, joiners, variation selectors), compatibility forms (full-width and styled letters), entities, percent-encoding and `\u` escapes, markup that splits a name (a .docx's runs), and any separator (hyphen, space, underscore, dot) between the words of a private repo or board name; the long names are also found inside a longer word (`<Name>Bot`, `<Name>2`); in UTF-8, in text saved as UTF-16 (with or without a byte-order mark), and in files that hold NULs. The list covers every team first name and persona name, full names too. A name that is not an everyday word counts in any case (`PEOPLE_ANY_CASE` in the script); a name that is also a common word or surname (`PEOPLE_CAPITALISED`, eleven of them) counts only when capitalised and whole. One product feature shares a name with a person; it is allowed in two named files, `GUARD_ALLOWED`, with the count pinned (one more fails). The same word is also the name of one page template. That is the one exception: the tool cannot tell a template from a person, so it allows exactly one use of the word in each of the three files listed in `TEMPLATE_NAME_PATHS` (each with its own exact count; a listed file that holds NULs, such as mixed encodings, is refused if it holds the word at all). A second use in a listed file is refused as "file #N: more uses of the page-template name than this file may hold (one). Remove the extra use, or ask for the limit to be raised"; the word in any other file is refused by file number as before, and every other listed word is still refused in those files. To add a path, add it to `TEMPLATE_NAME_PATHS` with the exact number of times the template name appears there, and add the path to `TEMPLATE_PATHS` in `tests/test_publish_public.py`; a file that only mentions the person never goes on the list. While either name check (this one or the real-names check) has not passed, the file list shows numbers only, never a path, and the commit message is not shown. A hit is reported as "file #N: a person's name" or "...a private repo or board name" or "...a hosting detail", never with the word. No Word, Excel or PowerPoint file with a listed word inside is accepted; none is tracked at present, and one that is added must be made again with neutral names.

## The checks

Nothing is pushed unless all of these pass. Each is checked before the push, and each refusal says why in plain words and exits with 1.

1. **Branch**: `clark-public` (the default), `release-X.Y.Z` (the digits 0 to 9 only, three numbers, nothing after: not a trailing new line, not other scripts' digits) or `main`. `main` also needs `--publish-main`.
2. **Target**: given with `--target` (there is no default; an address that is not well formed, such as an unclosed bracket, is a plain refusal), no password in it, not the private repo (read at run time from every remote of this checkout, the `url` and the `pushurl` of each, not only `origin`; compared by address and by name, in every https, ssh, `.git`, `www` and letter-case form), a public repo (asked of `gh`), and not changed by an `insteadOf` rule in your git settings. A folder is allowed only with `--allow-local-target`, which exists for the tests, and even then it is refused if it is this repo's own folder, another worktree or checkout of it, or any folder that shares its git store, if it is inside this repo's working tree, or if it contains this repo. A separate clone is allowed. Folders are compared by their identity on the disk (device and inode), not by the text of the path, so another letter case on a Mac (`/USERS/.../CLARK`, `.../CLARK/.git`) is still the same folder and is refused. Trailing `.git` is ignored however often it is repeated (`.git.git`, `.GIT/.git/`).
3. **Ref**: a tag or ref that is on `origin/main` (run `git fetch origin` first), and whose tests pass on both Pythons: the tool runs `dev/run_tests.py` for `python3` and `/usr/bin/python3` (change them with `--pythons`) on the files it is about to publish. They must be two different versions. The tests are not run at all if a script in the snapshot's `tests/`, `dev/`, `system/` or `src/` (`.py`, `.sh`, `.bash`, `.zsh`) starts headless Chrome without `--use-mock-keychain` and `--password-store=basic` (a launch is any string holding a launch flag, so a shell line such as `google-chrome ...` counts), or if one of them can't be read or parsed: that is a refusal (a Keychain dialog would appear on your screen, #104).
4. **Plain files**: no links or submodules, no file with the same name as another's folder, and nothing on the exclusion list (or `docs/public/`) left. The public README must be in the commit.
5. **Size**: no file over 5 MB.
6. **Private names**: the scrub above runs (the report says how many files it rewrote and that the private repo is untouched), then the guard refuses the snapshot if any listed word is left anywhere.
7. **Secrets**: no private key; no GitHub, AWS, Slack, Anthropic, OpenAI, Stripe live, Google API, npm or PyPI token; no JSON web token; no password in an address (a name, a colon and a password before the @ of a web or git address); no `Authorization: Bearer ...` line; no long password, key or token value, in quotes or not (`export API_KEY=...`, `password: ...`, `.npmrc` `_authToken=...`, `.pypirc` `password = ...`); and no `.env`, `.pem`, `.key`, `.keystore`, `id_rsa`, `.p12`, `.pfx`, `.git-credentials` or `credentials.json` file. It also looks inside what hides a secret: the parts of Word, Excel and PowerPoint files, and zips inside them (to four levels, 64 MB in all; anything deeper or bigger is a refusal, not a pass), text saved as UTF-16, and base64 (a private key's header, or a token, once decoded). The scan is deliberately wide: a false alarm is cheaper than a leak, so a harmless test value that looks like a secret should be built from pieces in the test (or renamed), not allowed. A normal test run applies the same scan to this repo's tracked files, so a false alarm shows there first.
8. **Real names**: the whole snapshot passes `tests/test_no_real_names.py` (every file, every path, every Office part, zips inside them to four levels, text saved as UTF-16, and a name with a zero-width space, soft hyphen or joiner inside it), and so do the commit's author, committer and message.
9. **One neutral commit**: exactly one new commit, author and committer `clark <clark@users.noreply.github.com>`, in UTC, with the message `clark <ref> (<short sha>)` (the short sha alone if the ref holds a listed word), built so that no git setting, signing, hook or environment variable of yours can change it.

A hit is shown only by number, never by name or path: "file #12 line 3" means line 12 of `git ls-tree -r --name-only <ref>`. Find it with:

    git ls-tree -r --name-only <ref> | sed -n '12p'

## If you stop it

Ctrl-C, `kill` (SIGTERM) and closing the terminal (SIGHUP) all stop the tool the same way: it removes its temporary folders, prints `INTERRUPTED` and exits with 130. A second Ctrl-C, `kill` or hang-up while it is removing them is held off (and the removal starts again if one gets in first), so the folder is not left behind. If the push had already started, look at the branch on the target to see whether it arrived; the tool never retries.

## Try it first (a dry run)

    python3 dev/tools/publish_public.py <tag or ref> --target git@github.com:<owner>/<repo>.git --dry-run

A dry run lists the files, runs the checks, says which commit it would make, and pushes nothing. It does not run the long tests unless you add `--with-tests`. It exits with 0 only if every check that ran passed, so it is also the pre-flight.

## Publishing

The first snapshot is cut by the Head by hand, with the same checks. After that:

    python3 dev/tools/publish_public.py v0.1.0 --target git@github.com:<owner>/<repo>.git

This goes to `clark-public`. The new commit sits on top of that branch's present tip, so the public history is a chain of snapshots. If the branch already holds exactly this snapshot, the tool says "Nothing to publish" and stops (exit 0). If someone else pushed in between, git refuses the push and nothing changes; run it again. When a push fails the tool prints one plain sentence and never git's own output (it can hold an address, a token or a name); run the push by hand to see that.

The published copy itself (`main`) is `--branch main --publish-main`.

## A release gate

`.github/workflows/tests.yml` runs on the public copy. Pushing a branch called `release-X.Y.Z` there is the gate: Linux (Python 3.9 and the newest) and macOS, at no charge.

    python3 dev/tools/publish_public.py v0.1.0 --target git@github.com:<owner>/<repo>.git --branch release-0.1.0

Then read the result:

    gh run list -R <owner>/<repo> --workflow tests.yml --branch release-0.1.0
    gh run view <run id> -R <owner>/<repo>

If it is green, the release is clean on three systems. If it fails, fix it in the private repo, merge, and publish again to the same branch: it becomes the next snapshot on top.

## When a check refuses

Nothing was pushed. Read the REFUSED line:

- **Private names left**: the report gives a file number and a kind. Find the file (below) and make a neutral change in the private repo: usually a name in code, a test label or a binary fixture. Never edit the tool's word lists to get past it.
- **Real names or secrets**: find the place (above), take the name or secret out of the private repo by a normal change, merge it, and run again. A secret that was ever committed counts as leaked; tell the owner.
- **Target**: check the address. Never aim it at the private repo, and never put a password in it.
- **Not on main**: merge the work first, or name a commit that is on `origin/main`.
- **Tests**: run `python3 dev/run_tests.py` and `/usr/bin/python3 dev/run_tests.py` and fix what fails.
- **Size**: leave the big file out, or keep it on the exclusion list if it is a private note.

Do not change the tool to get past a check. A change to this tool needs the owner's approval of the exact script.
