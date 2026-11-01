// The week a report covers (A-D2, prototype db.js:15 and views.js:507): the date the project keeps, or, when it keeps none, the
// coming Friday (today when today is a Friday). Pure: a day is read as a plain calendar day in UTC, so no time zone moves it.
// Stored and sent as YYYY-MM-DD; shown as DD-MM-YYYY.
export function comingFriday(iso) {
  const m = /^(\d{4})-(\d\d)-(\d\d)$/.exec(iso || "");
  if (!m) return "";
  const t = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]));
  t.setUTCDate(t.getUTCDate() + ((5 - t.getUTCDay() + 7) % 7));
  return t.toISOString().slice(0, 10);
}

export const weekOf = (stored, today) => (/^\d{4}-\d\d-\d\d$/.test(stored || "") ? stored : comingFriday(today));

export const shownDay = (iso) => (/^\d{4}-\d\d-\d\d$/.test(iso || "") ? iso.slice(8) + "-" + iso.slice(5, 7) + "-" + iso.slice(0, 4) : iso || "");
