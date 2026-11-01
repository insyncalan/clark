// The Edit parts, handed to the page as one object (`tools`). main.jsx passes this; view.jsx (the published page) passes nothing,
// so nothing under edit/ and neither stores/changes.js nor api.js is in a published file.
import { Gutter } from "./Gutter.jsx";
import { Add } from "./Add.jsx";
import { Title } from "./Title.jsx";
import { Toggle } from "./Toggle.jsx";
import { Toast } from "./Toast.jsx";
import { SneakPeek as Words, SneakButton as WordsButton } from "./SneakPeek.jsx";
import { PeekTabs, PeekActivity } from "./PeekActivity.jsx";
import { Cell } from "./cells/Cell.jsx";
import { Board, LayoutSwitch } from "./Board.jsx";
import { Publish } from "./Publish.jsx";
import { ProfileMenu, exportExcel } from "./ProfileMenu.jsx";
import { Personal } from "./Personal.jsx";
import { GLANCE } from "./GlanceEdit.jsx";
import { ClientFolder } from "./ClientFolder.jsx";
import { Movement } from "./Movement.jsx";
import { RichField } from "./RichField.jsx";
import { NeedsEdit } from "./NeedsEdit.jsx";
import { TrackerEdit } from "./TrackerEdit.jsx";
import { richOn } from "./richSave.js";
import { Safety } from "./Safety.jsx";
import { Diagnostics } from "./Diagnostics.jsx";
import { installPageErrors } from "./pageErrors.js";
import { Palette } from "./Palette.jsx";
import { AskSettings } from "./AskSettings.jsx";
import { askOn, setAsk, loadAsk } from "./askState.js";
import { AskPanel } from "./AskPanel.jsx";
import { installAskKeys, openPanel, closePanel, panelOpen } from "./askPanelState.js";
import { HelpLayer } from "../help/Help.jsx";
import { AddDialog } from "./AddDialog.jsx";
import { installKeys, openHelp, closeHelp, helpOpen } from "../help/helpStore.js";
import { templateEdit } from "./templates/index.js";

// Help (#82) is among them: a published file has no Help panel and no "?" key.
export const EDIT = { glance: GLANCE, Personal, RichField, NeedsEdit, TrackerEdit, richOn, Gutter, Add, Title, Toggle, Toast, Words, WordsButton, PeekTabs, PeekActivity, Cell, Publish, ProfileMenu, exportExcel, ClientFolder, Safety, Diagnostics, pageErrors: installPageErrors, AskSettings, ask: { on: () => askOn.value, set: setAsk, load: loadAsk }, MilestoneMore: Movement, Board, LayoutSwitch, HelpLayer, AddDialog, Palette, templateEdit, AskPanel, askPanel: { open: openPanel, close: closePanel, isOpen: () => panelOpen.value, installKeys: installAskKeys }, help: { open: openHelp, close: closeHelp, isOpen: () => helpOpen.value, installKeys } };
