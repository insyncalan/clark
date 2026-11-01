# Security policy

If you think you have found a security problem in clark, please tell us privately first, so it can be fixed before it is described in public.

## How to report a problem

- Email **alan@januscollab.com**.
- Or write by post to: the clark project, 3101 Park Blvd, Palo Alto, CA 94306, USA. Email is much faster, so please use it for a security problem.
- Please do not open a public issue or pull request for a security problem.
- Please say what you found, the steps to see it, which clark version and which computer (macOS version) you used, and what you think the harm could be.
- Please use made-up data when you test. Do not send us real client or project data.
- Please test only on your own copy of clark and your own files.

What to expect: we aim to reply within 5 working days, tell you whether we agree it is a problem, and tell you when it is fixed. We would like to thank you in the release notes if you want that.

## What clark stores, and where

- **Everything stays on your own computer.** clark keeps your work items, milestones and use cases in one database file, `clark.db`, in the system's app data folder (on a Mac, `~/Library/Application Support/clark`). Settings are beside it, and the daily log is in `~/Library/Logs/clark`.
- **Backups are on the same computer.** clark makes a daily copy of the database in a backups folder beside it. Keep clark's data folder out of folders that a service such as OneDrive syncs: if it is in one, that service copies your data, not clark.
- **Reports and Excel files are saved where you choose.** A published report is one self-contained HTML page. clark does not send it anywhere; you share it yourself.
- **clark listens on your own computer only.** The page you use is served on `127.0.0.1`, your own computer's private address, which other computers cannot reach. Every request for your data also needs a secret code (a token) that changes each time clark starts.
- **No account, and no data sent to us.** clark has no sign-in and no usage tracking, and the released app makes no connection to the internet of its own.
- **One feature sends text to an AI service, and only when you use it.** "Ask clark" sends the passages you ask about, and the AI menu sends the text you selected, to an AI service through the Claude command on your computer. Before anything is sent, the text is checked for passwords and keys, and a file that looks like it holds one is left out. clark checks whether that command is installed and works without it. clark itself makes no other connection to the internet, and nothing is sent to us. The browser window that shows clark, and any link you choose to open, are your browser's own.
- **Real client data is your responsibility.** All the data in this repository is made up. When you put your own data into clark, clark does not encrypt it; it is protected only by what your computer gives you, such as disk encryption (FileVault on a Mac).

## Supported versions

Until version 1.0, clark is in Beta. Only the **latest Beta release** gets security fixes. If you are on an older one, please update first and check the problem is still there.

## What we want to hear about

- **Yes:** problems in clark's own code in this repository, in the start-up file (`clark.command`), and in the report page it publishes.
- **Yes, but tell the maintainers too:** problems in the libraries clark bundles (they are listed in `NOTICE.md`). Please report those to the library's own maintainers as well, and tell us so we can update.

## What is outside

- Someone who can already read your files or run programs on your computer.
- Tricking a person into sharing their own data.
