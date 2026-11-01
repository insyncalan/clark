// The Edit parts, handed to the page as one object (`tools`). main.jsx passes this; view.jsx (the published page) passes nothing,
// so nothing under edit/ and neither stores/changes.js nor api.js is in a published file.
import { Gutter } from "./Gutter.jsx";
import { Add } from "./Add.jsx";
import { Title } from "./Title.jsx";
import { Toggle } from "./Toggle.jsx";
import { Toast } from "./Toast.jsx";
import { Cell } from "./cells/Cell.jsx";
import { Board, LayoutSwitch } from "./Board.jsx";
import { Publish } from "./Publish.jsx";
import { ProfileMenu } from "./ProfileMenu.jsx";
import { Personal } from "./Personal.jsx";
import { GLANCE } from "./GlanceEdit.jsx";
import { ClientFolder } from "./ClientFolder.jsx";
import { Movement } from "./Movement.jsx";
import { RichField } from "./RichField.jsx";
import { richOn } from "./richSave.js";
import { cleanHtml } from "../logic/cleanHtml.js";
import { Safety } from "./Safety.jsx";
import { HelpLayer } from "../help/Help.jsx";
import { AddDialog } from "./AddDialog.jsx";
import { installKeys, openHelp, closeHelp, helpOpen } from "../help/helpStore.js";

// Help (#82) is among them: a published file has no Help panel and no "?" key.
// `clean` is the page's own cleaner for a saved body that View draws as text (Section.jsx); a body it refuses draws as nothing.
const clean = (html) => { try { return cleanHtml(html || ""); } catch (e) { return ""; } };
export const EDIT = { clean, glance: GLANCE, Personal, RichField, richOn, Gutter, Add, Title, Toggle, Toast, Cell, Publish, ProfileMenu, ClientFolder, Safety, MilestoneMore: Movement, Board, LayoutSwitch, HelpLayer, AddDialog, help: { open: openHelp, close: closeHelp, isOpen: () => helpOpen.value, installKeys } };
