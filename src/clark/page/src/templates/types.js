// The section template store types (#96), in the store's order (store.SECTION_TYPES, section_kinds/__init__.py). Pure: no DOM, no
// Preact, so the catalogue (logic/templates.js) can read it without pulling in a component. tests/test_section_registry.py checks
// that this list, the store, the Python registry, the catalogue and the index (index.js) name the same eighteen types.
export const TEMPLATE_TYPES = [
  "textimage", "headline", "figures4", "figures3", "gallery", "table", "doclinks", "linkcard", "raid3", "raid4",
  "workitems", "callout", "imagecap", "quote", "contacts", "checklist", "keydates", "onedoc",
];

// Template types the page is ready for before the store takes them (#926 part 3): drawn by templateFor / templateEdit, but not in
// TEMPLATE_TYPES, which tests/test_section_registry.py holds equal to the store's list. The step that adds the type to the store
// (report_sections.type CHECK, section_kinds, publish rules) moves each id into TEMPLATE_TYPES, empties this list and turns the
// catalogue entry's `ready` on.
export const PENDING_TYPES = ["gantt"];
