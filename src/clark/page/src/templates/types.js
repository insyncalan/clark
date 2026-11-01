// The section template store types (#96), in the store's order (store.SECTION_TYPES, section_kinds/__init__.py). Pure: no DOM, no
// Preact, so the catalogue (logic/templates.js) can read it without pulling in a component. tests/test_section_registry.py checks
// that this list, the store, the Python registry, the catalogue and the index (index.js) name the same eighteen types.
export const TEMPLATE_TYPES = [
  "textimage", "headline", "figures4", "figures3", "gallery", "table", "doclinks", "linkcard", "raid3", "raid4",
  "workitems", "callout", "imagecap", "quote", "contacts", "checklist", "keydates", "onedoc",
];
