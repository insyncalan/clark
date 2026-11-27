"""The nightly's own commit of the refreshed shard times (development only; standard library only).

    python3 dev/tools/shard_commit.py --run-id ID [--file dev/tools/shard_times.txt] [--remote origin] [--push]

Run in a checkout of main after dev/tools/shard_refresh.py has rewritten the file. It makes ONE commit of that ONE file on the
branch shard-times-<run id> (the branch is new: it never writes over a branch that exists and never forces a push) and, with
--push, pushes the branch. It never touches main. The last line of the output is a JSON result: {"result": "done"|"noop",
"run_id", "branch", "sha", "pushed"}.

Exit 0: committed (and pushed when asked), or noop (the file did not change: no branch, nothing pushed). Exit 1: the push
was refused (a branch of that run already exists on the remote). Exit 2: not checked, nothing committed and nothing pushed:
the run id is not digits, the file is missing or holds no time, or another file changed too.

LIMIT: it commits a branch, it does not open the pull request. A pull request opened with the workflow's own token starts no
checks, so the branch is turned into a pull request by the pipeline's hands on GitHub (nightly_handover in Bifrost 2.0).
"""
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from shard_refresh import read_times

DEFAULT_FILE = "dev/tools/shard_times.txt"
BOT = ("github-actions[bot]", "41898282+github-actions[bot]@users.noreply.github.com")


def git(*args, check=True, env=None):
    r = subprocess.run(["git", *args], capture_output=True, text=True, env=env)
    if check and r.returncode:
        raise RuntimeError("git %s: %s" % (args[0], (r.stderr or r.stdout).strip()))
    return r


def refuse(why):
    print("Shard commit: not checked (%s); nothing committed, nothing pushed" % why)
    return 2


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--run-id", default="")
    ap.add_argument("--file", default=DEFAULT_FILE)
    ap.add_argument("--remote", default="origin")
    ap.add_argument("--push", action="store_true")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"\d{1,20}", a.run_id):
        return refuse("the run id %r is not digits" % a.run_id)
    path = Path(a.file)
    if not path.is_file():
        return refuse("%s is missing" % a.file)
    if not read_times(path.read_text(encoding="utf-8", errors="replace")):
        return refuse("%s holds no time" % a.file)
    changed = [ln[3:].strip().strip('"') for ln in git("status", "--porcelain", "--untracked-files=all").stdout.splitlines()]
    others = [p for p in changed if p != a.file]
    if others:
        return refuse("%d other changed file%s: %s" % (len(others), "" if len(others) == 1 else "s", ", ".join(others[:5])))
    branch = "shard-times-" + a.run_id
    if git("rev-parse", "--verify", "-q", "refs/heads/" + branch, check=False).returncode == 0:
        return refuse("a local branch %s exists" % branch)
    out = {"result": "noop", "run_id": a.run_id, "branch": None, "sha": None, "pushed": False}
    if changed:
        git("checkout", "-q", "-b", branch)
        git("add", "--", a.file)
        who = dict(os.environ, GIT_AUTHOR_NAME=BOT[0], GIT_AUTHOR_EMAIL=BOT[1], GIT_COMMITTER_NAME=BOT[0], GIT_COMMITTER_EMAIL=BOT[1])    # the commit is the bot's whoever runs this
        git("commit", "-q", "-m", "Shard times: refreshed from the real times of nightly run %s\n\nOne file, dev/tools/shard_times.txt, made by the nightly's shard-times job." % a.run_id, env=who)
        out.update(result="done", branch=branch, sha=git("rev-parse", "HEAD").stdout.strip())
        if a.push:
            pushed = git("push", a.remote, "%s:refs/heads/%s" % (branch, branch), check=False)
            if pushed.returncode:
                print("Shard commit: the push of %s was refused, nothing was overwritten (%s)" % (branch, (pushed.stderr or "").strip().splitlines()[-1:] or ""))
                return 1
            out["pushed"] = True
    print("Shard commit: %s" % ("committed %s on %s%s" % (out["sha"][:8], branch, " and pushed" if out["pushed"] else "") if changed else "noop, the file did not change"))
    print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
