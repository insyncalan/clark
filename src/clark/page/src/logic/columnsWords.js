// Row 1222: every new visible string of the column menu, as one named constant each. All are UNRULED: not yet ruled. The column names that were
// already a heading (Status, Item, Owner, Due, Priority; Date, Milestone, State, Progress) are not new and are not here.
export const UNRULED_MENU_LABEL = "Columns to show";
export const UNRULED_BUTTON = "Columns";
export const UNRULED_BUTTON_TIP = "Choose the columns";
export const UNRULED_LOCKED_REASON = "Always shown, so a row can be understood.";
export const UNRULED_STANDARD = "Show the standard columns";
export const UNRULED_ANNOUNCE = (label, on) => `${label} column ${on ? "shown" : "hidden"}.`;
export const UNRULED_ANNOUNCE_STANDARD = "Standard columns shown.";
