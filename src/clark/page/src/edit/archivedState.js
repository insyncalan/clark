// What the archived milestone's peek needs to be shared between the Archived box (which opens it) and the layer that draws it
// (edit/MsLayers.jsx, beside the page's own peek): the open row, and where focus goes back to. Memory only: it holds a copy of
// one archived row as last read, for the visit; it is never merged into the page's data, so no archived row can reach the Plan,
// the published file, the export or Ask.
import { signal } from "@preact/signals";

export const archivedOpen = signal(null);          // null, or { code, row, opener }

// How many work items and RAID items still point at a milestone (the prototype's "work items still linked").
export function linkedCount(d, id) {
  return [...((d && d.actions) || []), ...((d && d.raid) || [])].filter((r) => r.milestone === id).length;
}
