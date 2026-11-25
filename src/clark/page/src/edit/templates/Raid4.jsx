// RAID cards (item 96, row 1270), store type "raid4": its Edit part. Three or four across and up to eight cards (a body of version 2); an old body of version 1 reads as four across; every committed choice is
// one change() (one step, one Undo, place "report"). Given { section, tools }. The shared part is ./raidEdit.jsx.
import { RaidEdit } from "./raidEdit.jsx";
import { SIZES } from "../../templates/raid.js";

export const Edit = ({ section }) => <RaidEdit section={section} size={SIZES.raid4} choice />;
