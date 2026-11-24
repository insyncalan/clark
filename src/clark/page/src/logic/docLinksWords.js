// Row 1221, Cards: the two words on a file row in the editor's View. Both are UNRULED (not yet ruled).
export const UNRULED_OPEN = "Open";
export const UNRULED_DOWNLOAD = "Download";
// Item 1194, Documents and links: every visible string of the section, as one named constant each. All are ruled (16-11).
export const DESCRIPTION_LABEL = "Link description (required)";
export const NO_DESCRIPTION = (n) => `Link ${n}: Enter a link description.`;
export const BAD_TYPE = (name) => `${name}: That type of file can't be added. Use PDF, Word, Excel, PowerPoint, JPG, PNG or TXT.`;
export const OPEN = "Open";
export const DOWNLOAD = "Download";
export const ADD_FILE = "Add a file";
export const ADD_LINK = "Add a link";
export const LINK_ADDRESS_LABEL = "Link";
export const ADD_LINK_SUBMIT = "Add link";
export const CANCEL = "Cancel";
export const RENAME = (name) => (name ? `Rename ${name}` : "Rename");
export const MOVE_UP = (name) => `Move ${name} up`;
export const MOVE_DOWN = (name) => `Move ${name} down`;
export const REMOVE = (name) => `Remove ${name}`;
export const LINK_ADDED = "Link added";
export const MOVED = "Moved";
export const RENAMED = "Name saved";
export const NOTE = "A file is copied into the client folder's “Report files” folder and opens from the client's copy of the report.";
export const REMOVED = (name) => `Removed ${name}`;
export const REMOVED_FILE = (name) => `Removed ${name}. The file stays in the client folder.`;
// The mockup's note under the list (docs-mockup.html), verbatim.
export const ALLOWED_HEAD = "Files you can add:";
export const ALLOWED_TYPES = "PDF, Word (.doc .docx), Excel (.xls .xlsx .csv), PowerPoint (.ppt .pptx), JPG, PNG and TXT.";
export const NOT_HEAD = "Not allowed:";
export const NOT_TYPES = "HTML, SVG, ZIP and any program or script, because they can run code or hide what is inside. Links (to a SharePoint file, a web page or an email): https:// or mailto:.";
export const RENAME_HINT = "Name: click to rename, Enter saves, Esc cancels.";
// Row 1275, the drop area (all approved: NEW-WORDS Row 1275, 1773 and 1291).
export const DROP_OVER = "Drop files here to add them.";       // row 1593 (replaces "Drop a file here to add it.")
export const DROP_LINE = "Dropped files are kept in the client folder, in Report files.";
export const DROP_FOLDER = "Folders can't be added. Drop files, not folders.";       // row 1593 (replaces DROP_ONE "Drop one file at a time.")
export const DROP_TOO_BIG = "That file is larger than 25 MB, so it was not added.";
export const DROP_UNREAD = "That file could not be read from the drop. Reload the page and try again.";
export const DROP_MAX_BYTES = 25 * 1024 * 1024;
