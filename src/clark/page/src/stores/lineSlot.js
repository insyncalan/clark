// Where the app hands the filter line (#153) to the shared parts. The line's code is loaded only by the served page's entry
// (main.jsx), which sets `current` at start-up; a published file never does, so it holds none of the line's code or words.
export const lineApi = { current: null };
export function installLine(api) { lineApi.current = api; }
