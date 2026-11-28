// Row 1534: moving a Work items column. These are the ticket's words (the Product Manager's ruling of 24-11, comment 7126496638: "<Column> moved to position <N> of <M>"; the Classic menu has Move left and Move right lines and no Reset line: row 1499 pick 7B, changed by the ruling Q23 of 26-11, yes to Move left and Move right, no to Reset). The toast "Column moved. Undo" is dropped.
export const MOVED = (label, place, of) => `${label} moved to position ${place} of ${of}`;
export const MOVE_LEFT = "Move left";
export const MOVE_RIGHT = "Move right";
export const MOVED_LEFT = (label) => `Moved ${label} left`;
export const MOVED_RIGHT = (label) => `Moved ${label} right`;
// Kept apart from columnsWords.js: that file holds only UNRULED_ words (and the one ruled panel heading), and tests/test_table_columns.py pins that; these are ruled.
