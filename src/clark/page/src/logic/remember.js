// What a place remembers between visits (a zoom, how many rows, the Calendar or Timeline choice), in the browser's own storage,
// for this one browser only. Every read and write can fail (a private window, a blocked store, a file page): then nothing is
// remembered and the page still draws.
export function recall(key, fallback) {
  try {
    const t = window.localStorage.getItem(`clark.${key}`);
    return t === null ? fallback : JSON.parse(t);
  } catch (e) {
    return fallback;
  }
}

export function remember(key, value) {
  try { window.localStorage.setItem(`clark.${key}`, JSON.stringify(value)); } catch (e) { /* not remembered */ }
}
