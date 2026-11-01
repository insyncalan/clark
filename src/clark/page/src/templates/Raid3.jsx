// RAID cards, three (#96), store type "raid3": its view part. Up to three cards across, each a work item and the words chosen for it.
// View: text nodes only, never dangerouslySetInnerHTML; live rows only those logic/publishable.js keeps. isEmpty(section, data): true
// leaves the section out of the served View and the published file. The shared drawing is in ./RaidCards.jsx, the rules in ./raid.js.
import { RaidView, isEmptyCards } from "./RaidCards.jsx";
import { SIZES } from "./raid.js";

export const READY = true;
export const View = ({ section, data }) => <RaidView section={section} data={data} size={SIZES.raid3} />;
export const isEmpty = (section, data) => isEmptyCards(section, data, SIZES.raid3);
