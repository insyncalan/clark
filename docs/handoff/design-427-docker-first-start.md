# #427: install and first start, the Docker route

Status: design plus a first slice (a draft pull request). The change to `src/clark/server.py` (guarded) goes to the owner before it is merged.

## The problem

clark listens on 127.0.0.1 only, and refuses any request whose peer address is not 127.0.0.1 or ::1 (`csp_local`), whose Host is not this machine, or whose Origin or Sec-Fetch-Site is another site's. In a container with a published port, the browser's request does not arrive from 127.0.0.1. It arrives from the container network's gateway address, so clark would refuse every request.

## The two ways to fix it

### A. Host networking (`network_mode: host`)

- On Docker Desktop for Mac it exists from version 4.34, as an opt-in feature. It is **off by default**. You turn it on in Settings > Resources > Network > "Enable host networking", after signing in to a Docker account, then Apply and restart (Docker's own page).
- It supports TCP and UDP and Linux containers only. A container cannot bind the host's own network addresses with it. Docker's page does not say what "the host" is on a Mac (the Mac or Docker's hidden Linux machine), and does not say whether a listener on the container's 127.0.0.1 is then reachable from the Mac's browser. I could not confirm it without a real run, and no run was made.
- Colima and other Linux-VM tools do not give the Mac's network to a container this way.
- Security: `server.py` stays exactly as it is. This is its one real advantage.
- Cost: every first-time person must find a hidden setting and sign in to an account, for the sake of a feature Docker calls opt-in. That fails "easy".

### B. A container-only listen address

- clark binds 0.0.0.0 inside the container only when **both** `CLARK_CONTAINER=1` is set (the shipped Dockerfile sets it) **and** the container's marker file exists (`/.dockerenv`, or `/run/.containerenv` for Podman). Anywhere else, including the Mac, nothing changes.
- The compose file publishes the port as `127.0.0.1:8766:8766`. Only programs on the Mac itself can reach it, which is what the terminal route gives today.
- In container mode the peer check also accepts one more address: the container's default gateway, read from `/proc/net/route`. No other address is added.
- What the request looks like to clark: the browser goes to `http://127.0.0.1:8766/`, so the **Host is `127.0.0.1:8766` and the Origin (when sent) is `http://127.0.0.1:8766`**, exactly as now. The **peer** is the compose network's gateway (for example 172.18.0.1), because Docker's port forwarding makes the connection from outside the container. That is how Docker's forwarding is expected to work; **it has not been observed here** (Docker was not started, the machine's load was too high). The first real run must print the peer, and it goes on the hand-check sheet.
- The Host, Origin and Sec-Fetch checks, the token and every route are untouched.

### What B weakens, said plainly

1. Inside the container clark now listens on all of the container's addresses, not only loopback. Another container on the same Docker network can open a connection to it. It is refused (403), because its peer address is its own, not the gateway's. The compose file has no other service, and its network is private to this project.
2. The peer check no longer means "this very machine". It means "the container's gateway", which is Docker's forwarder. Anything that Docker forwards to the port arrives as that gateway. So the line `127.0.0.1:8766:8766` in the compose file is now a security control. If someone edits it to `8766:8766`, anyone on the network can reach clark, the peer check will not stop them, and only the Host check and the token remain. A test reads the compose file and fails if any published port lacks `127.0.0.1:`.
3. Any program on the Mac can already reach 127.0.0.1:8766 today, on the terminal route; B does not change that. Anyone who can run `docker` commands can already do far more than reach clark.
4. A browser page on another site still cannot talk to clark: Host, Origin and Sec-Fetch-Site are unchanged.

### Recommendation

**B.** The trade-off, first: B adds about 30 lines to a guarded file, lets clark listen on every address inside the container, and makes the compose file's `127.0.0.1:` a security control, in exchange for a route that works with Docker's default settings. A needs no change to `server.py`, but it is off by default, needs an account sign-in, and its behaviour on a Mac is not documented. B's added exposure is limited to the Docker network, and there it accepts one peer only.

## What is built in this slice

- `src/clark/server.py` (about 30 lines added, 3 changed): `container_mode()`, `container_gateway()`, `local_peer()`, the listen-address rule in `LocalServer`, and the bind in `serve`.
- `tests/test_server_container.py`: with no setting, nothing changes and non-loopback peers are refused; the setting alone, or the marker file alone, is not enough; in container mode the gateway and loopback pass and any other peer is refused; the Host and Origin checks hold for the gateway peer; the gateway is read from a route table; the compose file publishes to 127.0.0.1 only.
- `docker/Dockerfile` (python 3.12.12 slim, pinned by digest, non-root user 10001, only clark's files, a health check), `docker/Dockerfile.dockerignore` (only those files reach the build), `docker/compose.yaml`.

## Slice 2: clark starts on Linux inside the container

A container is Linux, and `platform.py` refused every system but the Mac: a run with the system named "linux" stopped at once with "Finding OneDrive on linux is not built yet". Slice 2 lets clark start there, in the shipped container and nowhere else on Linux.

### What changed (`src/clark/platform.py`)

- `container_mode()` (new): true only when `CLARK_CONTAINER=1` **and** `/.dockerenv` or `/run/.containerenv` exists. The same rule as `server.container_mode()` (which keeps its own copy so the guarded server imports nothing); a test fails if the two ever differ.
- `onedrive_roots()`: on Linux **and** in container mode, returns an empty list. On Linux outside a container (the setting alone, a marker file alone, or neither) it still raises `NotBuiltYet`; Windows still raises; the Mac branch is the same code as before and its tests are unchanged.
- `_only_mac()`: in a container, every other Mac-only call now says "X is not available when clark runs in Docker: it needs the Mac. Start clark the other way (clark.command) to use it" instead of "on linux is not built yet". It is still `NotBuiltYet`, so every caller that already handles it keeps working. Outside a container the old words are unchanged.
- Two small fixes to slice 1 that its own source test caught: the route table is opened with `encoding="utf-8"` in `server.py`, and the same in `tests/test_server_container.py`.

### Every other call on the start path (checked by starting clark for real with the system named "linux" and the container markers faked: `/health` answered 200 and the page loaded)

| Call | What happens in the container |
|---|---|
| `onedrive_roots()` (data folder check, store, settings, Ask, Word, publish) | empty list (the change) |
| `login_name()` | works anywhere; no change |
| `data_dir()` | still Mac-only, but the container always starts with `--data /data` (the Dockerfile's CMD), so it is never asked. Starting without `--data` stops with the Docker words above |
| `log_dir()` | `start_log` already catches the refusal: clark runs **without a daily log** (and `/api/diagnostics` and the log screen answer "not found"). Pointing the log into `/data` is a later slice |
| `never_read_places()` | Adding an Ask folder reaches it (`ask_folders.py`, `reach.never_inside`) and raises `NotBuiltYet` that nothing there catches; the server's catch-all answers it, so the person gets the generic error, not a plain sentence (**listed, not fixed, not hand-checked**). Ask itself already says "Questions work on a Mac for now" (`ask_claude`), so the feature is not offered to answer anyway |
| `open_file`, `reveal_file`, `open_url` | refused with the Docker words; the log screen and the page already turn that into a message. The container never opens a browser (the Mac-side starter does) |
| `choose_folder`, `choose_save_file`, `choose_open_file` | refused with the Docker words; Publish, Word export, Ask folders and section templates already show the refusal. Typing a folder path still works where the page offers it |
| `launcher_name`, `find_chrome`, `start_detached`, `open_app_window` | only used by `launch.py` (the Mac's `clark.command`); not on the container's start path |

### What the container mode loses, plainly

1. **The OneDrive refusal does not protect the shared data folder inside the container.** On the Mac clark refuses to keep its database in OneDrive (a synced folder can corrupt it). In the container there is no OneDrive app to find, so the check has nothing to compare with, and a data folder shared in from a OneDrive folder is **accepted**. The Mac-side starter (`clark-docker.command`, the follow-up) must check the folder before it starts the container and refuse a OneDrive path, using the same rule as the terminal route. Until it exists, the compose file's default folder (the terminal route's own, outside OneDrive) is the only protection, and a person who sets `CLARK_DATA` into OneDrive is not stopped.
2. The same empty list means Word import/export, Ask folders and publish also do not warn about a OneDrive place the person types.
3. No daily log, and no folder, Save or Open windows (see the table).
4. Outside a container nothing is gained: Linux still stops with "not built yet".

## The data folder

- The Mac's folder is shared in with a bind mount: by default `~/Library/Application Support/clark`, the terminal route's own folder, so both routes see the same data. They must not run at the same time. `CLARK_DATA` points the mount elsewhere.
- clark runs as user 10001, not root, with a read-only image, `cap_drop: ALL`, `no-new-privileges` and a small `/tmp`. These are untested until a real run.
- Docker Desktop shares `/Users` by default and presents the files as the person's own, so writing normally works. If it does not, run with `CLARK_UID=$(id -u) CLARK_GID=$(id -g)`. Colima is believed to share the home folder read-only by default; it needs the data folder mounted writable. Check this on a real run.
- Safety copies go to `backups` beside the database, so they live in the same shared folder.

## The browser

The container cannot open a browser. A Mac-side starter does it: a small `clark-docker.command` (follow-up) that checks Docker, runs `docker compose up -d`, waits for `/health`, then opens Chrome's app window (or the default browser) at `http://127.0.0.1:8766/`. It uses plain bash and `open`, so the Docker route does not need the Mac's Python. The idle stop (the server stopping when no window is left) needs `CLARK_LAUNCHED=1`; whether the container should stop itself that way is open.

## The health check

The image's health check asks `/health` from inside, with the right Host. `docker compose ps` shows "healthy". The starter script waits for it, and says what to do if it never comes.

## The first-run guide: "Docker or not"

Plain words, in `START-HERE.txt` (draft below). Docker Desktop's install:

- A download of a few GB, from docker.com.
- It asks for the Mac's admin password to set itself up, and for its own first-run steps. clark cannot do this silently.
- Its licence: free for personal use, small companies (fewer than 250 staff **and** under US$10 million a year) and open-source work; **paid above that, and for government bodies** (Docker's own FAQ). A consultancy or a client's machine may be over the line.
- **Colima** is a free alternative (command line, `brew install colima docker docker-compose`, then `colima start`). Harder to explain, so offered second.

## Questions for the owner

1. **Which route is the default?** The team's lead has ruled: Docker is the default, the terminal route the alternative. Please confirm. A reason to reconsider: the Docker route also needs the second slice above and the starter script, and clark's own needs (the Mac's Python and Chrome) are smaller than Docker's.
2. **Is Docker Desktop's licence acceptable for the people who will install clark?** My suggestion: yes for the guide to name it first, with the licence line and Colima named as the free alternative, since the guide cannot know the person's company size.

## Draft: the START-HERE section

```
Two ways to start clark. Pick one.

Way 1: with Docker (recommended if your computer already has it)
  Do you have Docker? Open Terminal and type:  docker --version
  If it answers with a version, go on. If it says "command not found", you do not have it yet:
    - Docker Desktop: download it from docker.com, open it, and give your Mac's password when asked. It is a large
      download. It is free for personal use and for companies with fewer than 250 people and under 10 million dollars a
      year; larger organisations must pay for it. Ask your IT team if you are not sure.
    - A free alternative: Colima (Terminal commands; see the clark help page).
  Then:
    1. Make sure Docker is running (its whale icon is in the menu bar, with no "starting" message).
    2. Double-click clark-docker.command in this folder.
    3. clark opens in your browser. To stop it, double-click stop-clark.command.
  If something is not right, it says what to do: Docker not installed, Docker not running, or "port 8766 is in use"
  (close the other clark window or program, then try again).

Way 2: without Docker
  Double-click clark.command (steps below).
```
(The two .command names are the plan; they are not built in this slice.)

## Not done, and why

- The Mac-side starter, the stop script, the START-HERE change in `dev/tools/package.py` and the download list (`release_files.py`, which the updater also reads): the download is a closed list with its own tests, and it should change in one reviewed step.
- Pointing the log into `/data`, and the OneDrive check in the Mac-side starter: see slice 2 above.
- No image was built and no container started: the machine's load was over 40 (91 at the start). Only the compose file was checked (`docker compose config`), and the guarded tests were run.
- The done-when in the issue (both routes tried on a clean Mac from the downloaded zip) is untouched.
