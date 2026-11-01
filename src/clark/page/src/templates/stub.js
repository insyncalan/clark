// What a section template's view part is before it is built (#96): it draws nothing, and isEmpty is always true, so Dashboard
// leaves the section out of the served View and the published file. A template's builder replaces its own file's parts, never this.
export function viewStub() {
  return { View: () => null, isEmpty: () => true };
}
