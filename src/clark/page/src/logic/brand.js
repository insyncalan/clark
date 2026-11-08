// Settings › Brands: plain functions and the card's words, no DOM and no Preact. The server (brands.py) decides and checks everything;
// a refusal comes with its own plain sentence and is shown as it is. Anything without one gets GENERIC. #944 T2.

export const GENERIC = "That didn't work, and nothing was changed. Try again, or restart clark.";
export const NOT_ANSWERING = "Nothing is answering. Check that the window clark runs in is still open, then reload the page.";
export const STALE = "This page is out of date because clark was restarted. Reload the page and try again.";
export const CANCELLED = "No file was chosen, so nothing was changed.";
export const TITLE = "Brands";
export const INTRO = "Add a brand from a file you were given, and clark uses its colours, fonts and pictures. Nothing changes until you choose Install.";
export const LOADING = "Looking for brands.";
export const EMPTY = "No brand is added, so the default look is used.";
export const REVIEW_HINT = "Looks in your Downloads folder for the newest brand file.";
export const CONFIRM_REMOVE = "Back to the default look";
export const LABELS = { review: "Review the brand in Downloads", choose: "Choose zip…", install: "Install", replace: "Replace", remove: "Remove",
  undo: "Undo", cancel: "Cancel", tryAgain: "Try again", added: "Added", replaced: "Replaced", removed: "Removed" };

const text = (v, n = 300) => (typeof v === "string" ? v.slice(0, n) : "");
const names = (v) => (Array.isArray(v) ? v.slice(0, 2000).map((n) => text(n)) : []);

// {status, body} → one sentence. Status 0 is no answer; 403 is a page from before clark was restarted.
export function answerWords(status, body) {
  if (status === 0) return NOT_ANSWERING;
  if (status === 403) return STALE;
  if (body && typeof body.message === "string" && body.message.trim() && body.message.length <= 600) return body.message;
  return GENERIC;
}

export const listView = (b) => ({
  brands: Array.isArray(b.brands) ? b.brands.slice(0, 500).map((x) => ({ id: text(x.id, 40), name: text(x.name, 200), version: text(x.version, 40) })) : [],
  undo: b.undo === true,
});

// The four files a brand holds, in plain words; a name not here is shown as it is.
const FILE_WORDS = { "clark-brand.json": "Brand details", "tokens.css": "Colours and fonts", "assets/cover.png": "Cover picture", "assets/logo.png": "Logo" };
export const fileWords = (n) => (FILE_WORDS[n] ? { label: FILE_WORDS[n], file: n } : { label: n, file: "" });

// The review as the panel draws it; "Replace" when the brand is already in the list, "Install" when it is new.
export function reviewView(r, installed) {
  const id = text(r.id, 40);
  return {
    id, name: text(r.name, 200), version: text(r.version, 40),
    replace: installed.some((x) => x.id === id),
    lists: [[LABELS.added, names(r.added)], [LABELS.replaced, names(r.replaced)], [LABELS.removed, names(r.removed)]],
  };
}
