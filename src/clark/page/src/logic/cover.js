// The report's cover band (A-D1): the project name, "Weekly report", the week-ending date and "for <client>". Every part is read
// from the project row the file already carries; a part with nothing to show is left out, never drawn empty. `today` (YYYY-MM-DD,
// the served page only, A-D2) gives a project that keeps no week the coming Friday, as the bar's Week ending field shows it; a
// published file passes none and shows only the week it was given.
import { weekOf } from "./week.js";

const dmy = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

export function coverLine(project, today = "") {
  const p = project || {};
  const parts = [];
  const week = String(today ? weekOf(p.week_ending, today) : p.week_ending || "").trim();
  const client = String(p.client_name || "").trim();
  if (week) parts.push(`Week ending ${dmy(week)}`);
  if (client) parts.push(`for ${client}`);
  return parts;
}
