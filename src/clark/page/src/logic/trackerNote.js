// The note an author sees in Edit when a tracker's weights do not add up to the whole (#189). It lives apart from logic/tracker.js on
// purpose: only Edit imports this file, so the words are never in the published file or in View (#451, "nothing internal").
import { fmt, WHOLE } from "./tracker.js";

// `t` is what totals() returns. "" when there are no lines or the weights add up to the whole.
export const weightsNote = (t) => (t.lines > 0 && t.weights !== WHOLE ? `Weights add up to ${fmt(t.weights)}%` : "");
