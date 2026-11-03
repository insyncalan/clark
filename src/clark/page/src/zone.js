// #631: the page's own time zone, sent to the server in the zone header (api.js on every call, app.js on "still here" every 10 seconds).
// Inside the shipped container the server reads its clock in this zone, so 'today' there is the person's day, not UTC's; a
// laptop that travels follows within a few seconds. The name is the browser's IANA one (Asia/Dubai), never a Windows zone id.
// On a Mac the server takes no notice of it. The published page (view.jsx) has no part of this.
export const ZONE_HEADER = "X-Clark-Tz";

// {header: name}, or {} when the browser can't say: then nothing is sent and the server keeps the zone it has.
export function zoneHeaders() {
  try {
    const name = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return typeof name === "string" && /^[A-Za-z][A-Za-z0-9_+\/-]{0,63}$/.test(name) ? { [ZONE_HEADER]: name } : {};
  } catch (e) {
    return {};
  }
}
