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
// Row 1534: the Work items column-moving words are ruled, so they live in columnOrderWords.js (this file holds only UNRULED_ words and the one ruled heading above);
// they are re-exported here so the menu reads every column-menu word from this one place.
export { MOVED, MOVE_LEFT, MOVE_RIGHT, MOVED_LEFT, MOVED_RIGHT } from "./columnOrderWords.js";
