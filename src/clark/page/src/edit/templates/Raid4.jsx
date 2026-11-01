// RAID cards, four (#96), store type "raid4": its Edit part. The same as three across with a fourth card; every committed choice is
// one change() (one step, one Undo, place "report"). Given { section, tools }. The shared part is ./raidEdit.jsx.
import { RaidEdit } from "./raidEdit.jsx";
import { SIZES } from "../../templates/raid.js";

export const Edit = ({ section }) => <RaidEdit section={section} size={SIZES.raid4} />;
