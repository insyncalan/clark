// The View menu's Group by and Swimlanes entries and what picking them says, shared by the editor's filter line and the published file's Group by
// (row 1533: one set of words). No import here writes anything, so the published file can use it.
import { work, setWork, announce } from "../stores/work.js";
import { GROUPS, LANE_GROUPS, groupLabel, boardGroup } from "../logic/board.js";
import { actionIcon, groupIcon } from "../menuIcons.js";

// The View menu's Group by and Swimlanes entries (row 812: Table and Board are the two-icon switch beside it; the prototype's words: "Group by", then on the board "Swimlanes" with
// "No lanes", "Workstream lanes", "Type lanes"; the lane Group by uses is not offered). `board` is false where there is no board.
export function layoutItems(w, board) {
  const onBoard = board && w.view === "board", g = onBoard ? boardGroup(w.group) : w.group;
  const lane = onBoard && w.lane && w.lane !== g && LANE_GROUPS.includes(w.lane) ? w.lane : "none";
  const out = [];
  out.push({ id: "lab-group", lab: "Group by", caps: true }, ...GROUPS.filter((x) => !onBoard || x.id !== "nothing").map((x) => ({ id: `group:${x.id}`, name: x.label, icon: groupIcon(x.id), checked: x.id === g })));
  if (onBoard) out.push({ id: "sep-lanes", sep: true }, { id: "lab-lanes", lab: "Swimlanes" }, { id: "lane:none", name: "No lanes", icon: actionIcon("none"), checked: lane === "none" },
    ...LANE_GROUPS.filter((x) => x !== g).map((x) => ({ id: `lane:${x}`, name: `${groupLabel(x)} lanes`, icon: groupIcon(x), checked: lane === x })));
  return { items: out, label: `Group by: ${groupLabel(g)}${lane !== "none" ? `, ${groupLabel(lane).toLowerCase()} lanes` : ""}` };
}

export function pickLayoutGroup(v) { const lane = work.value.lane; setWork({ group: v, lane: lane === v ? null : lane }); announce.value = `Grouped by ${groupLabel(v)}.`; }
export function pickLayoutLane(v) { setWork({ lane: v === "none" ? null : v }); announce.value = v === "none" ? "No lanes." : `${groupLabel(v)} lanes.`; }
