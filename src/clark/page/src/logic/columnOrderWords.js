// Row 1534: moving a Work items column. These are the ticket's words (the Product Manager's ruling of 24-11, comment 7126496638: "<Column> moved to position <N> of <M>"; the menu has no Move or Reset lines, the row 1499 pick 7B ruling). The toast "Column moved. Undo" is dropped.
export const MOVED = (label, place, of) => `${label} moved to position ${place} of ${of}`;
// Kept apart from columnsWords.js: that file holds only UNRULED_ words (and the one ruled panel heading), and tests/test_table_columns.py pins that; these are ruled.
