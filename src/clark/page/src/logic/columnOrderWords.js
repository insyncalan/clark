// Row 1534: moving a Work items column. These are the ticket's words (the Product Manager's ruling of 24-11, comment 7126496638: "Move left" and "Move right" are already in
// NEW-WORDS; "Reset to the standard order" and "<Column> moved to position <N> of <M>" are approved for the Head to log). The toast "Column moved. Undo" is dropped.
export const MOVE_LEFT = "Move left";
export const MOVE_RIGHT = "Move right";
export const RESET_ORDER = "Reset to the standard order";
export const MOVED = (label, place, of) => `${label} moved to position ${place} of ${of}`;
// Kept apart from columnsWords.js: that file holds only UNRULED_ words (and the one ruled panel heading), and tests/test_table_columns.py pins that; these are ruled.
