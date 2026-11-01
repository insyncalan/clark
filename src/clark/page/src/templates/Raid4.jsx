// RAID cards, four (#96), store type "raid4": its view part. The same as three across with room for a fourth card; the drawing is
// shared (./RaidCards.jsx). View: text nodes only; isEmpty(section, data) true leaves the section out of View and the file.
import { RaidView, isEmptyCards } from "./RaidCards.jsx";
import { SIZES } from "./raid.js";

export const READY = true;
export const View = ({ section, data }) => <RaidView section={section} data={data} size={SIZES.raid4} />;
export const isEmpty = (section, data) => isEmptyCards(section, data, SIZES.raid4);
