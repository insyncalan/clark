// Would this row be in the published file? The one page-side mirror of publish.select's `keep` (#96, FR-11: the served View shows
// exactly what the client sees). Pure: no DOM, no Preact. A section template's live part (figures, cards, a list of work items, a
// checklist line or a date from a milestone) asks this before it draws a row in the served View; the file itself only ever holds
// rows publish already kept. tests/test_section_registry.py runs it against publish.select over the same rows.
//
// publish.select keeps a row when: it is not archived (archived is 0), it is client visible where its kind has the column (every
// kind here), it is the project's own, its id is not in report_hidden, and none of its labels keeps it out (Sensitive, and any
// label whose behaviour or default choice is exclude). Every row of a kind whose own section is hidden is left out as well.

export const KINDS = ["milestones", "actions", "raid", "decisions", "use_cases"];
export const SECTION_OF_KIND = { milestones: "milestones", actions: "actions", raid: "raid", decisions: "decisions", use_cases: "usecases" };

const isZero = (v) => v === 0 || v === false;            // Python's `== 0`: 0 and False, never null, "0" or a missing field
const isOne = (v) => v === 1 || v === true;
// publish folds with casefold; upper then lower folds the long s, then the final sigma and ß (and ẞ) are folded by hand (to sigma and ss). tests/test_section_registry.py checks the two against each other.
const fold = (s) => String(s).toUpperCase().toLowerCase().replace(/\u03c2/g, "\u03c3").replace(/\u00df/g, "ss");

// The label names (folded) that keep a row out: Sensitive, and any label whose behaviour or default choice is exclude.
export function excludedLabels(rules) {
  const out = new Set(["sensitive"]);
  for (const r of rules || []) {
    if (r && (r.behaviour === "exclude" || r.default_choice === "exclude")) out.add(fold(r.name == null ? "" : r.name));
  }
  return out;
}

// The rules for one project, made once: { code, hidden (Set of ids), blocked (Set of folded label names), labels (id -> names),
// hiddenTypes (Set of the hidden sections' types) }.
export function rulesFor({ code, hidden = [], labelRules = [], labels = {}, sections = [] } = {}) {
  return {
    code,
    hidden: new Set(hidden || []),
    blocked: excludedLabels(labelRules),
    labels: labels || {},
    hiddenTypes: new Set((sections || []).filter((s) => s && isOne(s.hidden)).map((s) => s.type)),
  };
}

// One row of `kind` (one of KINDS), with the rules from rulesFor.
export function publishable(row, kind, rules) {
  if (!row || !KINDS.includes(kind) || !rules) return false;
  if (rules.hiddenTypes && rules.hiddenTypes.has(SECTION_OF_KIND[kind])) return false;
  if (!isZero(row.archived) || !isOne(row.client_visible)) return false;
  if ("project" in row && row.project !== rules.code) return false;
  if (rules.hidden.has(row.id)) return false;
  const names = Object.prototype.hasOwnProperty.call(rules.labels, row.id) ? rules.labels[row.id] : [];
  return !(names || []).some((n) => rules.blocked.has(fold(n)));
}

// The rows of `kind` in `data` that would be published, in their order.
export function keptRows(data, kind, rules) {
  return ((data && data[kind]) || []).filter((r) => publishable(r, kind, rules));
}
