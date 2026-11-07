// The note beside the Edit and View pill on the Gantt page (#928) while it is in Edit: the Dashboard's own words, drawn as its report bar draws them.
// An Edit part (tools.GanttBarNote), so a published file holds neither the note nor its class.
import { GANTT_EDIT_WORDS as W } from "./ganttWords.js";

export function GanttBarNote() {
  return <span class="rbar-state">{W.editNote}</span>;
}
