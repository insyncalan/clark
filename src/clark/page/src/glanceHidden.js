// Row 1303: a tile hidden with the eye leaves Edit view; it is shown again from the Add a tile menu. Plain functions, no imports.
// `tiles` are the tiles in order, each { key, hidden }. Project health is never listed here: it cannot be hidden on the At a glance
// section, and the glance template has its own button for it.

/** The tiles Edit draws: every tile that is not hidden, in order. */
export const drawnTiles = (tiles) => tiles.filter((t) => !t.hidden);

/** The tiles the Add a tile menu offers to show again: the hidden ones, in order, never Project health. */
export const hiddenTiles = (tiles) => tiles.filter((t) => t.hidden && t.key !== "health");
