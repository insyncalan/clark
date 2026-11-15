// Row 1179: the page's one AI client (talks to /api/ai/*) for the "Draft with AI" button and the right-click menu. Nothing is kept in the
// browser; the token is the page's own. A test may swap the client with setAiClient (the same two methods as aiClient.js's stub).
import { realAiClient } from "./aiClient.js";
import { token } from "../stores/report.js";

let client = realAiClient({ token });
export const aiClient = () => client;
export const setAiClient = (c) => { client = c; };
