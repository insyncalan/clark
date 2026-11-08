// Cleaned rich words, drawn as markup (row 1005). The one place a section template draws HTML: its caller hands it a string that is
// ALREADY clean, either the publish build's own output (a published file's `content`, cleaned by the server twice) or cleanHtml of the
// stored text (the page clark serves, through the `clean` prop Section.jsx gives a template view). Never given a stored string as it is.
// The template files themselves hold no dangerouslySetInnerHTML (tests/test_section_registry.py); this component is the audited seam.
export function CleanProse({ html, cls = "prose" }) {
  return <div class={cls} dangerouslySetInnerHTML={{ __html: html }} />;
}
