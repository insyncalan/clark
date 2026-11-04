// The week a report covers (A-D2, prototype db.js:15 and views.js:507): the date the project keeps, or, when it keeps none, the
// coming Friday (today when today is a Friday). item 570: the Friday comes from the board's own helper (board.js weekEndOf), so the bar
// and the board's This week never differ. Stored and sent as YYYY-MM-DD; shown as DD-MM-YYYY.
import { weekEndOf } from "./board.js";

export const weekOf = (stored, today) => (/^\d{4}-\d\d-\d\d$/.test(stored || "") ? stored : weekEndOf(today) || "");

export const shownDay = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso || "") ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso || "");
