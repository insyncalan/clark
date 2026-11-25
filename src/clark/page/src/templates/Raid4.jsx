// RAID cards (item 96, row 1270), store type "raid4": its view part. Four across and up to four cards (a body of version 1) or three or four across and up to eight (version 2); the drawing is
// shared (./RaidCards.jsx). View: text nodes only; isEmpty(section, data) true leaves the section out of View and the file.
import { RaidView, isEmptyCards } from "./RaidCards.jsx";
import { SIZES } from "./raid.js";

export const READY = true;
export const View = ({ section, data }) => <RaidView section={section} data={data} size={SIZES.raid4} />;
export const isEmpty = (section, data) => isEmptyCards(section, data, SIZES.raid4);
