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

/** True when it was kept; false when the store refused it (full, blocked), so a caller that must keep it can try less. */
export function remember(key, value) {
  try { window.localStorage.setItem(`clark.${key}`, JSON.stringify(value)); return true; } catch (e) { return false; }
}
