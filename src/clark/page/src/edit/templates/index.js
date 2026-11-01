// The section templates' Edit parts (#96): store type -> Edit component, all eighteen up front, so a template's builder changes only
// its own file here. Handed to the page as tools.templateEdit (edit/index.js); never in a published file.
import { TEMPLATE_TYPES } from "../../templates/types.js";
import { Edit as textimage } from "./TextImage.jsx";
import { Edit as headline } from "./Headline.jsx";
import { Edit as figures4 } from "./Figures4.jsx";
import { Edit as figures3 } from "./Figures3.jsx";
import { Edit as gallery } from "./Gallery.jsx";
import { Edit as table } from "./Table.jsx";
import { Edit as doclinks } from "./DocLinks.jsx";
import { Edit as linkcard } from "./LinkCard.jsx";
import { Edit as raid3 } from "./Raid3.jsx";
import { Edit as raid4 } from "./Raid4.jsx";
import { Edit as workitems } from "./WorkItemsList.jsx";
import { Edit as callout } from "./Callout.jsx";
import { Edit as imagecap } from "./ImageCap.jsx";
import { Edit as quote } from "./Quote.jsx";
import { Edit as contacts } from "./Contacts.jsx";
import { Edit as checklist } from "./Checklist.jsx";
import { Edit as keydates } from "./KeyDates.jsx";
import { Edit as onedoc } from "./OneDoc.jsx";

const EDITS = { textimage, headline, figures4, figures3, gallery, table, doclinks, linkcard, raid3, raid4, workitems, callout, imagecap, quote, contacts, checklist, keydates, onedoc };
export const TEMPLATE_EDITS = Object.freeze(Object.fromEntries(TEMPLATE_TYPES.map((t) => [t, EDITS[t]])));

// The Edit part for a section type, or null when it is not a template.
export function templateEdit(type) {
  return Object.prototype.hasOwnProperty.call(TEMPLATE_EDITS, type) ? TEMPLATE_EDITS[type] : null;
}
