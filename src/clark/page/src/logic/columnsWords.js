// Row 1222: every new visible string of the column menu, as one named constant each. All are UNRULED: not yet ruled. The column names that were
// already a heading (Status, Item, Owner, Due, Priority; Date, Milestone, State, Progress) are not new and are not here.
export const UNRULED_MENU_LABEL = "Columns";
export const UNRULED_BUTTON = "Columns";
export const UNRULED_BUTTON_TIP = "Choose the columns";
export const UNRULED_LOCKED_REASON = "Always shown, so a row can be understood.";
export const UNRULED_STANDARD = "Show the standard columns";
export const UNRULED_NEW_WORK = { id: "Id", type: "Type", workstream: "Workstream", milestone: "Milestone", raised: "Raised", closed: "Closed", usecase: "Use case", latest: "Latest update", wording: "Client wording" };
export const UNRULED_NEW_MILESTONES = { id: "Id", description: "Description", workstream: "Workstream", owner: "Owner", agreed: "Agreed", forecast: "Forecast", order: "Order", reason: "State reason" };
export const UNRULED_NOT_SET = "Not set";
export const UNRULED_ANNOUNCE = (label, on) => `${label} column ${on ? "shown" : "hidden"}.`;
export const UNRULED_ANNOUNCE_STANDARD = "Standard columns shown.";
