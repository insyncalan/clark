// Whether Change in words's words box is open (#42b). Memory only, never in the address.
import { signal } from "@preact/signals";

export const wordsOpen = signal(false);
export const askFrom = { el: null };      // what had focus before the first slash moved it into the footer input; the words box gives focus back to it

// The fields that just changed, { token, list: [{ref, field}] }, or null: the peek flashes them (set by stores/changes.js).
export const flashed = signal(null);
