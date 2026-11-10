-- clark.app (row 836): starts clark with no Terminal window. dev/tools/package.py mac --app compiles this with osacompile and puts
-- the clark folder (clark.command, the hidden .app program folder, clark-release.json) in Contents/Resources, so the app needs
-- nothing beside it: a quarantined download that macOS runs from a copy elsewhere still finds its own files.
-- It runs that clark.command, hidden, through bash: the launcher does every check and opens clark's window. What clark.command
-- and the launcher print is sent to the error output, so when clark.command stops with an error their own lines come back as
-- the error text, and the one dialog shows exactly that. Nothing here says anything of its own; OK is macOS's button.
on run
	set here to POSIX path of (path to me)
	set launcher to here & "Contents/Resources/clark.command"
	try
		do shell script "/bin/bash " & quoted form of launcher & " 1>&2"
	on error said
		display dialog said buttons {"OK"} default button "OK"
	end try
end run
