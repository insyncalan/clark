// Documents and links (#96), store type "doclinks": its view part. STUB: READY is false and it draws nothing (stub.js). Its builder fills this
// file, its Edit part (edit/templates/DocLinks.jsx), src/clark/section_kinds/doclinks.py and tests/test_tpl_doclinks.py, and nothing shared.
// View: text nodes only, never dangerouslySetInnerHTML; links, pictures, files and dates through ./safe.js; live rows only those
// logic/publishable.js keeps. isEmpty(section, data): true leaves the section out of the served View and the published file.
import { viewStub } from "./stub.js";

export const READY = false;
export const { View, isEmpty } = viewStub();
