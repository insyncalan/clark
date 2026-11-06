// The Edit parts, handed to the page as one object (`tools`). main.jsx passes this; view.jsx (the published page) passes nothing,
// so nothing under edit/ and neither stores/changes.js nor api.js is in a published file.
import { Gutter } from "./Gutter.jsx";
import { Add } from "./Add.jsx";
import { Title } from "./Title.jsx";
import { Toggle } from "./Toggle.jsx";
import { Toast } from "./Toast.jsx";
import { SneakPeek as Words, SneakButton as WordsButton } from "./SneakPeek.jsx";
import { PeekTabs, PeekActivity } from "./PeekActivity.jsx";
import { PeekLatest, PeekWarn, PeekNeeded } from "./PeekLatest.jsx";
import { Cell } from "./cells/Cell.jsx";
import { Eye } from "./cells/Eye.jsx";
import { Board } from "./Board.jsx";
import { ArchivedItems, ArchivedPill } from "./ArchivedItems.jsx";
import { BulkActions, BulkLayer, installBulk } from "./Bulk.jsx";
import { Publish } from "./Publish.jsx";
import { ReportBar } from "./ReportBar.jsx";
import { ProfileMenu, exportExcel } from "./ProfileMenu.jsx";
import { ProjectSwitch } from "./ProjectSwitch.jsx";
import { DemoBanner, NewProjectButton } from "./Demo.jsx";
import { ExportBtn } from "./ExportBtn.jsx";
import { ImportBtn } from "./ImportBtn.jsx";
import { Personal } from "./Personal.jsx";
import { Data } from "./Data.jsx";
import { Boxes } from "./Boxes.jsx";
import { ReviewDays } from "./ReviewDays.jsx";
import { GLANCE } from "./GlanceEdit.jsx";
import { ClientFolder } from "./ClientFolder.jsx";
import { Movement } from "./Movement.jsx";
import { MilestonesPage } from "./MilestonesPage.jsx";
import { MsAdd } from "./MsAdd.jsx";
import { MilestoneEdit } from "./MilestonePeek.jsx";
import { RichField } from "./RichField.jsx";
import { NeedsEdit } from "./NeedsEdit.jsx";
import { DocumentsEdit } from "./DocumentsEdit.jsx";
import { TrackerEdit } from "./TrackerEdit.jsx";
import { RichRead } from "./RichRead.jsx";
import { ItemRowsEdit } from "./ItemRowsEdit.jsx";
import { richOn } from "./richSave.js";
import { cleanHtml } from "../logic/cleanHtml.js";
import { Safety } from "./Safety.jsx";
import { Update } from "./Update.jsx";
import { Projects } from "./Projects.jsx";
import { RowMenu } from "./RowMenu.jsx";
import { UseCasesPage } from "./UseCasesPage.jsx";
import { UCEDIT } from "./UseCasesEdit.jsx";
import { Diagnostics } from "./Diagnostics.jsx";
import { PublishedReports } from "./PublishedReports.jsx";
import { installPageErrors } from "./pageErrors.js";
import { Palette } from "./Palette.jsx";
import { AskSettings } from "./AskSettings.jsx";
import { People } from "./People.jsx";
import { askOn, setAsk, loadAsk } from "./askState.js";
import { AskPanel } from "./AskPanel.jsx";
import { installModeKeys } from "./keys.js";
import { GanttTitle } from "./GanttTitle.jsx";
import { installAskKeys, openPanel, closePanel, panelOpen } from "./askPanelState.js";
import { HelpLayer } from "../help/Help.jsx";
import { HelpButton } from "../help/HelpButton.jsx";
import { SearchButton } from "./SearchButton.jsx";
import { AskButton } from "./AskButton.jsx";
import { AddDialog } from "./AddDialog.jsx";
import { addItem } from "./addItem.js";
import { MsEye } from "./MsEye.jsx";
import { MsAddBack } from "./MsAddBack.jsx";
import { MsLayers } from "./MsLayers.jsx";
import { ArchivedMilestones } from "./ArchivedMilestones.jsx";
import { HelpPeek } from "../help/HelpPeek.jsx";
import { addOverlay } from "../components/pick.js";
import { installKeys, openHelp, closeHelp, helpOpen, setCloseOthers, closeContext } from "../help/helpStore.js";
import { effect } from "@preact/signals";

// One right-hand panel at a time: the Help peek closes the ask panel as it opens, and the ask panel opening closes the Help peek.
setCloseOthers(() => closePanel());
addOverlay("#help-peek");                                   // Esc and clicks in the Help peek are the peek's, not the Work selection's
effect(() => { if (panelOpen.value) closeContext({ focus: false }); });
import { pictureUrl } from "../help/helpPictures.js";
import { templateEdit } from "./templates/index.js";
import { HAND_OVER } from "./HandOver.jsx";

// Help (#82) is among them: a published file has no Help panel and no "?" key.
// `clean` is the page's own cleaner for a saved body that View draws as text (Section.jsx); a body it refuses draws as nothing.
const clean = (html) => { try { return cleanHtml(html || ""); } catch (e) { return ""; } };
export const EDIT = { clean, DemoBanner, NewProjectButton, glance: GLANCE, Personal, Data, Boxes, ReviewDays, RichField, RichRead, NeedsEdit, DocumentsEdit, TrackerEdit, ItemRowsEdit, richOn, Gutter, ExportBtn, ImportBtn, ArchivedItems, ArchivedPill, ProjectSwitch, Add, Title, GanttTitle, Toggle, Toast, Words, WordsButton, PeekTabs, PeekActivity, PeekLatest, PeekWarn, PeekNeeded, Cell, Eye, Publish, ReportBar, ProfileMenu, PublishedReports, exportExcel, ClientFolder, Safety, Update, Projects, Diagnostics, pageErrors: installPageErrors, AskSettings, People, ask: { on: () => askOn.value, set: setAsk, load: loadAsk }, MilestoneMore: Movement, MilestonesPage, MsAdd, MilestoneEdit, MsEye, MsAddBack, MsLayers, ArchivedMilestones, UseCasesPage, ucEdit: UCEDIT, Board, RowMenu, HelpLayer, HelpButton, SearchButton, AskButton, HelpPeek, AddDialog, addItem, Palette, templateEdit, AskPanel, modeKeys: { install: installModeKeys }, askPanel: { open: openPanel, close: closePanel, isOpen: () => panelOpen.value, installKeys: installAskKeys }, help: { open: openHelp, close: closeHelp, isOpen: () => helpOpen.value, installKeys, pictureUrl }, Bulk: { Actions: BulkActions, Layer: BulkLayer, install: installBulk }, HandOver: HAND_OVER };
