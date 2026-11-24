// Row 1222: every new visible string of the column menu, as one named constant each. All are UNRULED: not yet ruled. The column names that were
// already a heading (Status, Item, Owner, Due, Priority; Date, Milestone, State, Progress) are not new and are not here.
export const UNRULED_MENU_LABEL = "Columns";
export const UNRULED_BUTTON = "Columns";
export const UNRULED_BUTTON_TIP = "Choose the columns";
export const UNRULED_LOCKED_REASON = "Always shown, so a row can be understood.";
export const UNRULED_STANDARD = "Show the standard columns";
export const UNRULED_ANNOUNCE = (label, on) => `${label} column ${on ? "shown" : "hidden"}.`;
export const UNRULED_ANNOUNCE_STANDARD = "Standard columns shown.";
// Row 1499: the heading of the Work items menu panel and the menu's aria-label in the Classic look (ruled). The Columns button's own label and tip above are not changed.
export const PANEL_HEADING = "Columns to show";
// Row 1534: moving a Work items column. These are the ticket's words (the Product Manager's ruling of 24-11, comment 7126496638: "Move left" and "Move right" are already in
// NEW-WORDS; "Reset to the standard order" and "<Column> moved to position <N> of <M>" are approved for the Head to log). The toast "Column moved. Undo" is dropped.
export const MOVE_LEFT = "Move left";
export const MOVE_RIGHT = "Move right";
export const RESET_ORDER = "Reset to the standard order";
export const MOVED = (label, place, of) => `${label} moved to position ${place} of ${of}`;
