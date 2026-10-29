// The Edit parts, handed to the page as one object (`tools`). main.jsx passes this; view.jsx (the published page) passes nothing,
// so nothing under edit/ and neither stores/changes.js nor api.js is in a published file.
import { Handle } from "./Handle.jsx";
import { Options } from "./Options.jsx";
import { Add } from "./Add.jsx";
import { Title } from "./Title.jsx";
import { Toggle } from "./Toggle.jsx";
import { Toast } from "./Toast.jsx";
import { Publish } from "./Publish.jsx";
import { ClientFolder } from "./ClientFolder.jsx";
import { HelpLayer } from "../help/Help.jsx";
import { installKeys, openHelp, closeHelp, helpOpen } from "../help/helpStore.js";

// Help (#82) is among them: a published file has no Help panel and no "?" key.
export const EDIT = { Handle, Options, Add, Title, Toggle, Toast, Publish, ClientFolder, HelpLayer, help: { open: openHelp, close: closeHelp, isOpen: () => helpOpen.value, installKeys } };
