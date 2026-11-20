// Row 1295: the person's own slash commands for the / menu, read from the server when the panel opens (the files are kept by ask_commands_service.py).
// The menu lists the ones that can run from the box as it is: an answer, anywhere, with no {input} (what is typed after the name is not carried by the menu yet).
// {today} is filled when the menu is drawn. A project's own command with the same name wins in that project.
import { signal } from "@preact/signals";
import { menuCommands } from "../logic/askShortcuts.js";
import { askCommandsRead } from "./publishApi.js";

export const ownCommands = signal([]);

export async function loadOwnCommands(code) {
  const r = await askCommandsRead(code);
  const b = r.body;
  ownCommands.value = r.status === 200 && b && b.ok === true && Array.isArray(b.all) ? menuCommands(b) : [];
}
