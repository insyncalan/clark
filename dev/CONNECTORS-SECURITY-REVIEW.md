# ask clark connectors: security review (Row 1306)

Scope: the connectors that ask clark may read when the person turns them on in Settings (Microsoft 365: Mail, Calendar, Teams, SharePoint and OneDrive; Todoist is listed but cannot be read, see finding F3). Read-only review of the code on `origin/main` (c6ae7ff20) plus the fixes in this change. Nothing was run against a real connector: this box is Linux and the command only runs on a Mac (`ask_claude.py` `command()`), so every statement marked "code and fake command" is proved by tests with a faked command, and every statement marked "not verified" needs a Mac with Microsoft 365 connected.

## Threat model (the ticket's eight points)

| # | Point | Where it is held | Verdict |
|---|---|---|---|
| 1 | Hostile content (a mail, chat or file can hold instructions) | Results screened in `ask_connector_screen.py` `screen()` (hidden characters refused, `MAX_RESULT` 40000, `MAX_TOTAL` 70000); every tool call and result checked in `ask_connector_stream.py` `inspect()`; a refused result refuses the whole run. The request now says results are data (`ask_claude.py` `CONNECTOR_NOTE`, F1). | Held in code and fake command. Whether a real model obeys the note is not verified. |
| 2 | What leaves the computer | Off by default (`connector_switches`), a project can turn one off (`store.py` `connector_allowed`: Off wins), the Used line names what was read (`ask_connector_screen.py` `used_line`). With nothing On the call is the locked-down one (`test_ask_connector_wiring`). | Held. |
| 3 | Read only, each part its own switch | `ask_connector_args.py` `READ_TOOLS` (allowed by exact name per part) and `WRITE_TOOLS` (denied by name); every known claude.ai server but the On one denied whole by prefix (`KNOWN_SERVERS`). | Held for the named tools. Two gaps: F4 (`read_resource`), F5 (a server not in `KNOWN_SERVERS`). |
| 4 | Which tools the command may use | Allow-list form `--tools ToolSearch` (probe F3b on a real laptop: the init event lists `["ToolSearch"]`), `--allowedTools=` for the exact read tools, `--disallowedTools=` for the rest; the init event must be exactly `[ToolSearch]` or the run is refused (`init_problem`). | Held, as probed. See F5 for what the allow-list does not cover. |
| 5 | Credentials | clark keeps no password or key. The child gets a built-from-nothing environment (`child_env`: `HOME`, `USER`, `LOGNAME`, `LANG`, fixed `PATH`, pinned switches). The discovery command (`mcp list`) uses the same environment and only the name and status of each line are read (`ask_connectors.py`). Only switch state is stored (`connector_switches`, `project_connectors`). | Held. |
| 6 | Client output | A change after a connector run needs the approval panel and the separate Confirm (F2, fixed here). A DRAFT line is shown beside the panel and is not in the report until the person adds it; it is not marked as read from a connector (F6, open). | Change cards held after the F2 fix; F6 open. |
| 7 | Logging | Nothing is logged by the connector modules (`test_ask_connector_hostile` `test_nothing_logged`, `test_nothing_printed`). The ticket says the log "may" name the connector and the time; no log exists. | Held (nothing leaks); the optional log is not built. |
| 8 | Docker | `ClaudeCommand.command()` refuses in a container (`platform.container_mode()`), so no connector run starts there. | Held. |

## Findings fixed in this change (each with a test)

- **F1. The request did not say tool results are data.** `ask.RULES` rule 1 treats only passages as data and rule 2 says "You have no tools". In a connector run the model has tools and their results are text anyone can write. Fix: a fixed note in front of the request of a connector run only (`ask_claude.py` `CONNECTOR_NOTE`, applied in `answer()`); a run with no connector is byte-identical to before. Test: `tests/test_ask_connector_data_note.py`.
- **F2. A change after a connector run did not need the separate Confirm.** `AskService.hold` marked a reply `from_source` only when a folder passage was sent, so a change suggested after the model read a mail or a Teams chat could be applied with Apply alone. The ticket (test 5) wants the extra tick. Fix: `hold(..., from_connector)` marks the reply when the run had a connector in it (`ask_service.py`). Test: `tests/test_ask_connector_change_gate.py`; the mutant in `tests/test_ask_change_route.py` takes the new argument.
- **F7. The shown words said the opposite of what the code now does.** The first-run card and Help said ask clark "never reads your mail, Teams or calendars". With a connector On that is false. The ticket's step 3 had not been done (the ticket says the prototype already has the sentence; the plan repo's prototype and mock-ups do not, checked by search). Changed in `askWords.js` and `helpContent.json` (2 places) to the decided sentence. Test: `tests/test_ask_connector_words_1306.py`, and `tests/test_ask_first_run_1292.py` updated.

## Findings not fixed here

- **F3. Todoist can be turned On and is never read.** `READ_TOOLS` has no Todoist table, so a Todoist switch that is On leaves the call locked down (pinned by `test_ask_connector_wiring` `test_todoist_alone_has_no_allow_table_so_it_is_exactly_today`). The person sees On and nothing is used or said. Todoist read tool names were never probed. Needs a ruling: hide the switch, or probe and build.
- **F4. `read_resource` is allowed under SharePoint and OneDrive.** It is a general resource reader of the Microsoft 365 server. Whether it can read a mail or calendar resource when only SharePoint is On is not verified. Needs a Mac with Microsoft 365: call it with a mail resource address while only SharePoint is On.
- **F5. A claude.ai server that is not in `KNOWN_SERVERS` is not denied by flag.** Only the stream check catches a call to it, after the fact (comment in `ask_connector_args.py`). Whether the command in print mode refuses a deferred tool that is neither allowed nor denied is not verified. Needs a Mac: connect a server not in the list and ask the model to call one of its write tools.
- **F6. A DRAFT line from a connector run is not marked.** The draft opens beside the panel and nothing is in the report until the person adds it, but unlike a change it has no extra tick. The ticket says connector content may reach a report only through the approved change cards. Needs a ruling (drop the draft in a connector run, or word a warning); a warning is a shown word, so it was not invented here.

## The not-yet-verified items from the ticket (spike comment, 18-11)

| Item | State now |
|---|---|
| Built-in tools really refused with the flag set | The flag set changed to `--tools ToolSearch` (probe F3b: init lists only `ToolSearch`). The run is refused if the init event lists anything else (`init_problem`, `test_ask_connector_c4c`). Code and fake command: verified now. Real run of the final argument list: not verified. |
| A denied M365 write tool refused when Claude tries to call it | The stream check refuses any call to a tool not on the read list of a part that is On (`test_ask_connector_wiring` `test_a_write_tool_called_refuses_even_with_a_clean_result`). The command itself refusing the call: not verified (needs a Mac). |
| One run with the whole real flag set together | Not verified (needs a Mac with Microsoft 365). |
| Run-time check that the Mail tool is visible, refusing the ask if not | Done by reading the ToolSearch result in its real shape (`search_result_ok`: one `tool_reference` block per tool, `tool_use_result.matches` equal) and the init event. Code and fake command: verified now. |

## Decision

Connectors may ship as built (off by default, read only, per project turn-off, change gate) once F1, F2 and F7 are merged. F3 to F6 and the Mac checks above are open; F4 and F5 are the ones that could let a hostile mail reach something the person did not turn On, so they should be settled by a run on a Mac before a release that contains connectors is called reviewed.
