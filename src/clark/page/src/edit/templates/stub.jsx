// What a section template's Edit part is before it is built (#96): a labelled empty state, in words. Edit only: this folder is
// never in a published file (edit/index.js hands it to the page as tools.templateEdit). A builder replaces their own file, never this.
// It names no template: a template the box does not offer yet is not named on the page (its words are held with Help's).
export const STUB_WORDS = "This template can't be filled in yet. It stays out of the published page, so you can remove it or keep it for later.";
export function editStub() {
  return function Edit() {
    return <p class="quiet tpl-stub">{STUB_WORDS}</p>;
  };
}
