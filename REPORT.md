# #948 owner name on one line (Work items, Edit)
Changed: src/clark/page/src/edit/edit.css (editor-only): the owner picker's name is nowrap with an ellipsis, above 640 px (the small-screen card keeps wrapping by word). Due: its date is already one line; the second line ("In 5 days") is the designed words line, left as is.
Test: tests/test_edit_cells_layout.py (owner now one line, box no taller than 30, right edge inside its cell; waits for document.getAnimations() to be empty). Fails on main, passes here; 1400 and 900, light and dark.
Run: test_edit_cells_layout (1 test), test_movement_in_view (3), test_movement_page (15): all pass.
Published page: not affected (edit.css is not in page-view.html; shell.css untouched).
Not verified: a name wider than the column in a real long-name project (demo names only); a name clipped to the ellipsis is read in full by its button label, there is no hover title (no new words).
