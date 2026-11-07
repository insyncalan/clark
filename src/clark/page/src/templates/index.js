// The section templates' view parts (#96): store type -> { view, isEmpty, ready }. Filled with all eighteen up front, so a
// template's builder changes only its own <Type>.jsx, never this file, Section.jsx or Dashboard.jsx. Section.jsx draws a template
// section through templateFor(type) (its Edit part comes from tools.templateEdit, edit/templates/, never in a published file);
// Dashboard.jsx leaves it out of the served View and the published file while isEmpty is true.
import { TEMPLATE_TYPES, PENDING_TYPES } from "./types.js";
import * as textimage from "./TextImage.jsx";
import * as headline from "./Headline.jsx";
import * as figures4 from "./Figures4.jsx";
import * as figures3 from "./Figures3.jsx";
import * as gallery from "./Gallery.jsx";
import * as table from "./Table.jsx";
import * as doclinks from "./DocLinks.jsx";
import * as linkcard from "./LinkCard.jsx";
import * as raid3 from "./Raid3.jsx";
import * as raid4 from "./Raid4.jsx";
import * as workitems from "./WorkItemsList.jsx";
import * as callout from "./Callout.jsx";
import * as imagecap from "./ImageCap.jsx";
import * as quote from "./Quote.jsx";
import * as contacts from "./Contacts.jsx";
import * as checklist from "./Checklist.jsx";
import * as keydates from "./KeyDates.jsx";
import * as onedoc from "./OneDoc.jsx";
import * as gantt from "../components/GanttSection.jsx";

const MODULES = { textimage, headline, figures4, figures3, gallery, table, doclinks, linkcard, raid3, raid4, workitems, callout, imagecap, quote, contacts, checklist, keydates, onedoc };

export const TEMPLATE_PARTS = Object.freeze(Object.fromEntries(TEMPLATE_TYPES.map((t) => [t, Object.freeze({
  view: MODULES[t].View, isEmpty: MODULES[t].isEmpty, ready: MODULES[t].READY === true,
})])));

// The parts of the types the page is ready for before the store takes them (types.js PENDING_TYPES).
const PENDING_MODULES = { gantt };
export const PENDING_PARTS = Object.freeze(Object.fromEntries(PENDING_TYPES.map((t) => [t, Object.freeze({
  view: PENDING_MODULES[t].View, isEmpty: PENDING_MODULES[t].isEmpty, ready: PENDING_MODULES[t].READY === true,
})])));

// The parts for a section type, or null when it is not a template (text, glance, needs and the other built-in types).
export function templateFor(type) {
  const has = (o) => Object.prototype.hasOwnProperty.call(o, type);
  return has(TEMPLATE_PARTS) ? TEMPLATE_PARTS[type] : has(PENDING_PARTS) ? PENDING_PARTS[type] : null;
}

// Whether a template section has nothing to show (FR-11: the served View and the published file decide alike). A section that is
// not a template answers false; a template whose isEmpty throws counts as empty, so it is left out rather than half drawn.
export function templateEmpty(section, data) {
  const t = templateFor(section && section.type);
  if (!t) return false;
  try { return t.isEmpty(section, data) !== false; } catch (e) { return true; }
}
