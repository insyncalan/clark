// RAID cards, three (#96), store type "raid3": its view part. STUB: READY is false and it draws nothing (stub.js). Its builder fills this
// file, its Edit part (edit/templates/Raid3.jsx), src/clark/section_kinds/raid3.py and tests/test_tpl_raid3.py, and nothing shared.
// View: text nodes only, never dangerouslySetInnerHTML; links, pictures, files and dates through ./safe.js; live rows only those
// logic/publishable.js keeps. isEmpty(section, data): true leaves the section out of the served View and the published file.
import { viewStub } from "./stub.js";

export const READY = false;
export const { View, isEmpty } = viewStub();
