// Item 1194, Documents and links: every new visible string of the section, as one named constant each. All are UNRULED: not yet
// ruled, except the three the ticket quotes (the description label, "Enter a link description." and the empty state).
export const UNRULED_DESCRIPTION_LABEL = "Link description (required)";
export const UNRULED_NO_DESCRIPTION = "Enter a link description.";
export const UNRULED_EMPTY = "Nothing here yet. Add a file or a link.";
export const UNRULED_BAD_TYPE = "That type of file can't be added. Use PDF, Word, Excel, PowerPoint, JPG, PNG or TXT.";
export const UNRULED_OPEN = "Open";
export const UNRULED_DOWNLOAD = "Download";
export const UNRULED_ADD_FILE = "Add a file";
export const UNRULED_ADD_LINK = "Add a link";
export const UNRULED_LINK_ADDRESS_LABEL = "Link";
export const UNRULED_ADD_LINK_SUBMIT = "Add link";
export const UNRULED_CANCEL = "Cancel";
export const UNRULED_RENAME = (name) => (name ? `Rename ${name}` : "Rename");
export const UNRULED_MOVE_UP = (name) => `Move ${name} up`;
export const UNRULED_MOVE_DOWN = (name) => `Move ${name} down`;
export const UNRULED_REMOVE = (name) => `Remove ${name}`;
export const UNRULED_LINK_ADDED = "Link added";
export const UNRULED_MOVED = "Moved";
export const UNRULED_RENAMED = "Name saved";
export const UNRULED_NOTE = "A file is copied into the client folder's “Report files” folder and opens from the client's copy of the report.";
export const UNRULED_REMOVED = (name) => `Removed ${name}`;
export const UNRULED_REMOVED_FILE = (name) => `Removed ${name}. The file stays in the client folder.`;
// The mockup's note under the list (docs-mockup.html), verbatim.
export const UNRULED_ALLOWED_HEAD = "Files you can add:";
export const UNRULED_ALLOWED_TYPES = "PDF, Word (.doc .docx), Excel (.xls .xlsx .csv), PowerPoint (.ppt .pptx), JPG, PNG and TXT.";
export const UNRULED_NOT_HEAD = "Not allowed:";
export const UNRULED_NOT_TYPES = "HTML, SVG, ZIP and any program or script, because they can run code or hide what is inside. Links (to a SharePoint file, a web page or an email): https:// or mailto:.";
export const UNRULED_RENAME_HINT = "Name: click to rename, Enter saves, Esc cancels.";
