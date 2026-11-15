// The Milestones library template (row 1192), store type "milestoneslib": its view part. The Dashboard's Milestones block, drawn as the
// built-in section draws it (components/MsBlock.jsx: the Timeline / Calendar switch, the list, the legend), from the report's milestones,
// as a section of its own: it does not need the built-in Milestones section to be on the page. It carries no content of its own. isEmpty:
// no milestone is shown, so the served View and the published file leave the section out, as the published file leaves out the built-in.
import { data as reportData, fromFile, asAt } from "../stores/report.js";
import { milestoneRows, todayIso } from "../logic/milestones.js";
import { leftOutIds } from "../logic/picker.js";
import { MsBlock } from "./MsBlock.jsx";

export const READY = true;

export const isEmpty = (section, data) => {
  const d = data || reportData.value;
  const client = fromFile.value;
  const left = new Set(client ? [] : leftOutIds(d));
  return milestoneRows(d.milestones, client && asAt.value ? asAt.value : todayIso(), client).filter((r) => client || (r.clientVisible && !left.has(r.id))).length === 0;
};

export function View({ section }) {
  return <MsBlock place={`sec-${section.id}`} />;
}
