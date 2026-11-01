// RAID cards, three (#96), store type "raid3": its Edit part. Up to three cards, each a work item and where its text comes from;
// every committed choice is one change() (one step, one Undo, place "report"). Given { section, tools }. The shared part is ./raidEdit.jsx.
import { RaidEdit } from "./raidEdit.jsx";
import { SIZES } from "../../templates/raid.js";

export const Edit = ({ section }) => <RaidEdit section={section} size={SIZES.raid3} />;
