# Design note: an optional backup copy folder (#622, guarded)

Guarded files touched: `src/clark/backup.py` and `src/clark/server.py` (one route and its size limit, three lines). `store.py`,
`schema.sql`, `history.py` and `changes.py` are not touched, and there is **no database migration**. Review: Full (two readers,
never the builder).

## Plain words, for the owner

People keep files in OneDrive to have them backed up. For clark that means one person who wants a copy that is not only on the
laptop. It does not mean several people sharing one database, and the live database must never sit in OneDrive: it is written to
all the time, and OneDrive can copy it half-way through a write. So clark does two things. The live data folder is still refused
inside OneDrive, and the refusal now says what to do: choose a backup folder in OneDrive instead. And Settings › Backups gets an
optional box, "Copy my backups to", which is off until a folder is typed in. Each time clark makes a backup it also puts the same
finished file in that folder, with the same name, and tidies that folder the same way (the same number kept). It writes the file
under a temporary name and gives it its real name only when it is whole, so OneDrive never sees half a file. If the folder is
missing, full or locked, clark says so in plain words under Settings › Backups; your save and the backup on this computer still
succeed. To get a copy back, `python3 -m clark restore --from FOLDER NAME` reads it from that folder (on a new computer too).

## Where the setting lives, and why there is no migration

The folder is one more key in the data folder's `settings.json`, beside the backups number and the profile name and email
(`settings.py`), written the same way (read, change one key, replace the whole file in one step, and never replace a file that
cannot be read). `settings.json` is a per-computer file by design (it is never inside the database), which is right here: a copy
folder is a fact about this computer and its OneDrive, and it must not travel inside a backup or a restored database. The
`app_settings` table was rejected: it needs a column, so a migration step, and the step numbers 12, 13 and 14 are already
claimed. Nothing in the schema changes.

Saved value: `backup_copy_folder`, an absolute path as typed (a leading `~` is accepted and written out in full). Missing or
unusable means off.

## The rules for the folder (`settings.set_backup_copy_folder`, and again at every copy)

Refused, in plain words ending "Nothing was changed.", with nothing written:
- not an absolute path (or `~`), or longer than 1,000 characters, or holding a control character;
- the live data folder, inside it, or the live backups folder (compared after following links, so a shortcut does not get round it);
- a file where the folder should be, or a folder this account cannot write to;
- a folder that does not exist and cannot be made (a missing last folder is made, never anything above it that is a file).

OneDrive is allowed here, on purpose. Because the setting file can also be edited by hand, the same checks run again at every
copy, and a failure is a warning, never a stop.

## The data flow of one backup copy (`backup.copy_out`)

1. `make` (and `finish`, for the copy taken before an undo or an import, once that step has really kept it) has a finished,
   checked single file in the live backups folder. This is the only thing ever copied: never the live database, `-wal` or `-shm`.
2. The copy goes to a private temporary name in the copy folder (`.clark-...part`, the same shape retention already tidies up), is
   read back and compared with the source (size and checksum; no database is opened inside OneDrive), and is then moved to the
   real name with a plain rename. A name that is already there is left as it is (never replaced).
3. Retention runs in the copy folder with the data folder's own number kept (`prune(..., keep=settings.backups_kept)`). It only
   ever removes a file whose whole name is clark's backup naming (`NAME`), so a person's other files in that folder are safe, as
   in the live folder. A working file a day old is tidied the same way.
4. Success clears any earlier copy warning.

## Failure behaviour

Any problem (folder missing, locked, full, refused by the rules above, the read-back not matching) makes `copy_out` give up, remove
its temporary file, keep a plain warning in `backup.copy_warning` and log it once (the folder is written from `~`, as the existing
daily warning is, so no user name is logged). The live backup and the save are never affected: `copy_out` never raises. The
warning is shown under Settings › Backups with the daily-copy warning (`GET /api/backups`, key `copy_warning`) and goes when a copy
works or the setting is cleared. The next backup tries again.

## Restore from the copy folder

`backup.bring_in` checks a named file in the copy folder (a whole clark backup name, a regular file, not a link, and a good
database by `store.check_copy`) and copies it into the live backups folder; `python3 -m clark restore --from FOLDER [NAME]`
lists the folder or does that and then runs the ordinary restore from the live folder. So nothing is ever written to the copy
folder by a restore (no `replaced-` folder in OneDrive), the old database is kept as usual, and a corrupt or foreign file is
refused. On a new computer there is no `settings.json`, so the folder is named on the command line. `backup.restore_into` (a
copy into a fresh, empty data folder) also reads from any folder.

## What is not built

- **Docker.** There is no Docker route in this repository, so this is documentation only. The mounted data folder must stay on
  the computer's own disk, and the backup folder is mounted as a second, separate folder, for example
  `-v "$HOME/Library/CloudStorage/OneDrive-<name>/clark backups:/backups"`, then typed into Settings as `/backups`.
- **The Mac-side starter check.** It is not built here. The typed command, for the owner to run on his own laptop and for the
  starter check to copy, which refuses a data folder under OneDrive or CloudStorage:
  `case "$(cd "$DATA" && pwd -P)" in "$HOME"/Library/CloudStorage|"$HOME"/Library/CloudStorage/*|"$HOME"/OneDrive*) echo "Keep clark's data off OneDrive: choose a backup folder in OneDrive instead."; exit 1;; esac`
- A folder chooser button, and a list in Settings of the copies in the copy folder (the command line reads it; the page lists the
  live backups folder as before).
