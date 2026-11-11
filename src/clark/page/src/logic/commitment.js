// issue 709: a use case's commitment, the owner's three words (Planned 2026, Committed, Planned 2027) or none. The WORDS come from the server
// (data.commitments, and use_case.commitment); this file only reads them and names the chip's look. A file made by 1.0.0 has no key:
// that reads as none, and nothing is drawn.
export const commitWord = (u) => (u && typeof u.commitment === "string" && u.commitment.trim() ? u.commitment.trim() : "");

/** The class that gives a word its look ("Planned 2027" -> "cc-planned-2027"); a word the page does not know gets the plain outline. */
export const commitClass = (word) => "cc-" + String(word).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

/** The words the person may choose, from the data the server sent (never typed into the page). */
export const commitWords = (d) => (d && Array.isArray(d.commitments) ? d.commitments.filter((w) => typeof w === "string" && w) : []);
