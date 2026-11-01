// The report's cover band (A-D1): the project name, "Weekly report", the week-ending date and "for <client>". Every part is read
// from the project row the file already carries; a part with nothing to show is left out, never drawn empty.
const dmy = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso) ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso);

export function coverLine(project) {
  const p = project || {};
  const parts = [];
  const week = String(p.week_ending || "").trim();
  const client = String(p.client_name || "").trim();
  if (week) parts.push(`Week ending ${dmy(week)}`);
  if (client) parts.push(`for ${client}`);
  return parts;
}
