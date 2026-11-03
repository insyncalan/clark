// Test-only (tests/test_tracker_logic.py): the progress tracker's pure logic on a bare page, never part of clark's bundle.
import * as tracker from "@src/logic/tracker.js";
import * as edit from "@src/logic/trackerEdit.js";
import { weightsNote } from "@src/logic/trackerNote.js";

// `tracker` is the reader's file with the author's on top: WORDS and ALL_WORDS cover both, and the line checks are the author's.
window.K = { tracker: { ...tracker, ...edit }, weightsNote };
