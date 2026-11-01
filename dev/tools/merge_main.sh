#!/usr/bin/env bash
# merge_main.sh: merge origin/main into the checked-out branch and rebuild the generated pages. Run BY HAND; it is not a
# hook, installs nothing, writes no git config, and never pushes.
#
# Why: every merge of main dirties many open PRs, because the generated pages (src/clark/page/page.html and page-view.html)
# conflict. A git merge DRIVER cannot fix it: git runs the driver while the working tree still holds the PRE-merge sources
# (the page files sort before src/, and the other files are not merged on disk yet), so the driver builds from stale
# sources and the merge looks clean with a stale page (build_page.py --check then says both pages are out of date).
#
# By-hand form of the same thing:
#   git merge -m "Merge origin/main" origin/main || { [ -z "$(git diff --name-only --diff-filter=U | grep -vE '^src/clark/page/(page|page-view)\.html$')" ] && git checkout --theirs src/clark/page/page.html src/clark/page/page-view.html && python3 dev/tools/build_page.py >/dev/null && git add src/clark/page/page.html src/clark/page/page-view.html && git commit -q --no-edit; }
#
# Exit codes: 0 done (or already up to date), 1 refused or stopped.

MSG="Merge origin/main"
PAGES="src/clark/page/page.html src/clark/page/page-view.html"
PAGE_RE='^src/clark/page/(page|page-view)\.html$'

say() { printf '%s\n' "$*"; }
refuse() { say "Refused: $*"; exit 1; }

git rev-parse --git-dir >/dev/null 2>&1 || refuse "this is not a git checkout."
cd "$(git rev-parse --show-toplevel)" || exit 1

git symbolic-ref -q HEAD >/dev/null || refuse "HEAD is detached. Check out a branch first."
[ -z "$(git status --porcelain)" ] || refuse "the working tree is not clean. Commit or stash your changes first."

say "Fetching origin..."
git fetch origin || refuse "git fetch origin failed."

if git merge-base --is-ancestor origin/main HEAD; then
  say "Already up to date with origin/main. Nothing merged."
  say "Not pushed. Run the checks, then push once."
  exit 0
fi

rebuild() {
  python3 dev/tools/build_page.py >/dev/null || return 1
  # shellcheck disable=SC2086
  git add $PAGES
}

if git merge -m "$MSG" origin/main; then
  say "Merged cleanly."
  if python3 dev/tools/build_page.py --check >/dev/null 2>&1; then
    say "Pages are up to date."
  else
    say "A clean merge left the pages out of date. Rebuilding."
    rebuild || { say "Stopped: the page build failed. The merge is committed; the pages are not rebuilt."; exit 1; }
    git commit -q --amend --no-edit || exit 1
    say "Pages rebuilt and added to the merge commit."
  fi
else
  unmerged="$(git diff --name-only --diff-filter=U)"
  others="$(printf '%s\n' "$unmerged" | grep -vE "$PAGE_RE" | grep -v '^$')"
  if [ -n "$others" ] || [ -z "$unmerged" ]; then
    say "Stopped on conflicts. The merge is still in progress."
    if [ -n "$others" ]; then say "Other conflicting files:"; printf '  %s\n' $others; else say "The merge failed without a file conflict (see git's message above)."; fi
    say "Resolve them and commit, or undo with: git merge --abort"
    exit 1
  fi
  say "Only the generated pages conflict. Taking main's copies and rebuilding."
  # shellcheck disable=SC2086
  git checkout --theirs $PAGES || exit 1
  rebuild || { say "Stopped: the page build failed. The merge is still in progress (git merge --abort to undo)."; exit 1; }
  git commit -q -m "$MSG" || exit 1
  say "Pages rebuilt and the merge committed."
fi

say "Not pushed. Run the checks, then push once."
exit 0
