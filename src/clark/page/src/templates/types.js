// The section template store types (#96), in the store's order (store.SECTION_TYPES, section_kinds/__init__.py). Pure: no DOM, no
// Preact, so the catalogue (logic/templates.js) can read it without pulling in a component. tests/test_section_registry.py checks
// that this list, the store, the Python registry, the catalogue and the index (index.js) name the same eighteen types.
export const TEMPLATE_TYPES = [
  "textimage", "headline", "figures4", "figures3", "gallery", "table", "doclinks", "linkcard", "raid3", "raid4",
  "workitems", "callout", "imagecap", "quote", "contacts", "checklist", "keydates", "onedoc",
];

// Template types that have a page part but no section_kinds module, because they carry no content of their own (row 926: the Gantt
// section draws the project's Gantt lines). Drawn by templateFor / templateEdit, taken by the store (changes.py NEW_SECTION_TYPES,
// layout 19) and offered by logic/templates.js ACCEPTS, but not in TEMPLATE_TYPES, which tests/test_section_registry.py holds equal to
// the registry's list.
export const PENDING_TYPES = ["gantt"];
