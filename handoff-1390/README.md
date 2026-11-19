# Row 1390 Excel export redesign: handoff from Banner (19-11, parked: not Tech Debt)

Base: origin/main b209d657 (all three slices were cut from it; main has moved since, so expect to merge main).
Ticket: clark-plan 1390 (section "Decided by Alan"); mock-up clark-plan mockups/1390-excel-export-redesign. Python only plus helpContent.json.

- Slice 1 = the code in this branch's first commit (tokens, colours, headings, aliases; excel.py, excel_colours.py, excel_client.py, excel_cover.py, excel_import.py, excel_palette.py, helpContent.json, dataCard.js, 44 files with tests). Built in a working tree, never committed there: UNTESTED as a whole (no full run recorded, no ci_scan, no mutation sweep).
- Slice 2 = handoff-1390/s2.patch (Report + Documents sheets; 23 files; excel_picture.py, ExcelLayout.jsx, tests). `git apply` against origin/main; it overlaps slice 1 files (excel.py, excel_client.py, excel_cover.py, helpContent.json, dataCard.js), so apply it after slice 1 and resolve by hand. Working tree only: UNTESTED.
- Slice 3 = handoff-1390/s3.patch (client export by source pinned, Help text of what the client copy leaves out); was one local commit 603b595e on main b209d657. Commit body has no test lines: UNTESTED.
- Not done anywhere: the round-trip import test on an OLD workbook (a generator of old-format workbooks was planned: not built), the mutation sweep on the new logic, ci_scan, the merge-speed test set, any browser check, PR bodies.
