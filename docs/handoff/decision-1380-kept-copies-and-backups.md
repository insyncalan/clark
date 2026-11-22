# Decision: kept copies of publications go with 'Copy my backups to' only (row 1380)

Status: decided by the Head (ruling of 20-11, Dubai), recorded here. No behaviour change.

## What is decided

- The local backup (`backup.take`, written beside clark.db) does not carry the folder `published-copies`.
- A kept publication (published_copies.py) is copied out only when Settings > Backups > 'Copy my backups to' is set. `backup._copy_worker` and `backup._copy_kept` copy each kept file there once, into its `published-copies` folder, and never again.
- With no copy folder set, the kept copies live only in the data folder, beside clark.db, and are in no backup.
- A restore (`backup.restore_path`) never removes or changes a kept copy (tests/test_backup_copy.py, test_a_restore_never_removes_a_kept_publication).
- Kept copies are never pruned (published_copies.py).

## Why

The local backups are small copies of the database for undo, import and bug cases. Kept pages can be many and large and are never pruned; carrying them in every local backup would multiply them on the same disk, which does not protect against losing the disk. The one place that protects against that is the optional copy folder, so the kept copies go there.

## What follows from it

- After a restore, a publication number the restored database gives out again can meet a kept copy of another page. A visit then gets 409 copy_changed and nothing is shown. This is intended, and is tested end to end in tests/test_past_reports.py (test_a_real_restore_that_reuses_a_number_for_another_page_is_refused_on_the_visit), using the real `backup.restore_path`.
- The words for the Backups card and Help that say this to the user are pending approval (row 1380 part a). Until then the card and Help do not say it.
