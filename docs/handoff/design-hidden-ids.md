# Design note: the eye on each milestone row (Edit)

No guarded file is touched. `src/clark/store.py` is unchanged.

## What is added
In Edit, each row of the Milestones list (the Dashboard's Milestones section and the Milestones page) has an eye: a real button beside the row that leaves the milestone out of the published page, or puts it back. On the Milestones page a left-out row stays and says so in words ("Left out of the published page"), so the state is never colour alone. On the Dashboard (#436) the eye takes the milestone off the block (the row, the timeline and the Calendar), the block draws only what is on the page, in View too, and "+ Add a milestone from your project record (N)" (Edit) opens the picker for milestones and brings them back with one `pick` change and one Undo. View and a published file have no eye and no mark.

## Where the state comes from
`Store.data_for(code)` already returns `report_hidden`: the sorted ids of this project's rows that the eye has left out (added for the templates, #96). The page reads that list, so after a reload, a change or an Undo the eye is drawn from what clark saved and the page keeps no copy of its own. Nothing new is read or sent by the server.

## Writes
The eye sends the page's existing change, kind `report_hidden`, op `new` (leave out) or `delete` (include again), through the same change and Undo routes as before. One press is one change and one Undo. A second press on the same row while the first is on its way is ignored.

## What the published file never carries
The published file is made from `publish_inputs`, which leaves the hidden rows out before anything is written. `tests/test_milestones_eye.py` publishes a project with a left-out milestone and checks the file holds neither its name nor the eye, the mark or `report_hidden`.

## Known limits
On the Milestones page the left-out mark is in the list only; the timeline and the Calendar show no mark for a left-out milestone. The eye's name changes with the state ("Leave out of..." / "Include in..."), so it has no aria-pressed.

## Also in this change
The progress figure on each milestone row is text with a hidden bar picture, clamped to 0 to 100, and "Not set" when there is no number (`tests/test_milestones_dashboard.py`).
