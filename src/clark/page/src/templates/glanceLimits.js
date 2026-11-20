// Glance template (row 1264, slice 5): the limits of a bespoke tile, the page's copy. Pure: no DOM, no Preact. The server holds the same
// numbers in section_kinds/glancetemplate.py (BESPOKE_MAX, LABEL_MAX, FIGURE_MAX, TAG_MAX, NOTE_MAX) and enforces them in check(); this copy
// only stops a person typing past them. tests/test_tpl_glance_store_1264.py fails when the two differ. Limits count characters (code points).
export const BESPOKE_MAX = 12;
export const LABEL_MAX = 40;
export const FIGURE_MAX = 12;
export const TAG_MAX = 12;
export const NOTE_MAX = 60;
export const TONES = ["green", "amber", "red", "blue", "neutral"];

// Characters as the server counts them: a code point is one, not two UTF-16 units.
export const chars = (s) => Array.from(typeof s === "string" ? s : "").length;
export const within = (s, most) => chars(s) <= most;
