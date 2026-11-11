// The Settings pages (item 1024): Edit's own, so a published file holds none of their names. Views.jsx reads them from tools.SettingsPages.
// "published" is the one entry that is not a Settings page: choosing it opens the Published reports page of its own (view published, row 1087), see Views.jsx.
// [group, [[address key, name, tools drawn (in order), heading that takes the focus]]]
export const GROUPS = [
  ["Everyday", [["projects", "Projects", ["Projects"], "projects-h"], ["people", "People", ["People"], "people-h"], ["published", "Published reports", ["PublishedPage"], "pubs-h"], ["profile", "Profile", ["Profile"], "profile-h"], ["feedback", "Feedback", ["Feedback"], "feedback-h"]]],
  ["Publishing", [["folder", "Folder", ["ClientFolder"], "client-folder-h"], ["brand", "Brand", ["Brands"], "brands-h"]]],
  ["Look and feel", [["appearance", "Appearance", ["Personal"], "personal-h"], ["reports", "Reports", ["ReviewDays", "GanttSetting"], "review-days-h"]]],
  ["Data and safety", [["backups", "Backups", ["Safety"], "safety-h"], ["export", "Export and import", ["Data"], "data-card-h"]]],
  ["Advanced", [["claude-ai", "Claude and AI", ["AskSettings"], "ask-settings-h"], ["logs", "Logs and diagnostics", ["Diagnostics"], "diagnostics-h"], ["version", "Version and updates", ["Update", "Quit"], "update-h"]]],
];
export const ADVANCED_NOTE = "These are for setting up Claude, and for when something goes wrong. Most people never need them.";      // item 1024: said once, under the Advanced heading
export const NEEDS_PROJECT = ["ClientFolder", "PublishedPage", "ReviewDays", "GanttSetting"];      // cards that need an open project; a page is left out when any of its cards is
