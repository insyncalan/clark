// Which picker is open ("<id>:<field>" of a table cell, "peek:<id>:<field>" of a peek chip), or "". One lives at a time. Kept in a store of its
// own so the peek's chips (a published file's bundle too) can share it with the table's cells (edit/cells/Cell.jsx) without pulling the Edit part in.
import { signal } from "@preact/signals";

export const openCell = signal("");
