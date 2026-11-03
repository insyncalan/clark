// Test-only (tests/test_filter_line.py): the filter line's pure logic on a bare page, never part of clark's bundle.
import * as fl from "@src/logic/filterLine.js";
import * as filters from "@src/filters.js";
import * as tiles from "@src/glanceTiles.js";
import * as report from "@src/stores/report.js";
import "@src/lineInstall.js";            // the app installs the line at start-up; the page under test does the same
import { lineText } from "@src/stores/line.js";
window.T = { fl, filters, tiles, report: { ...report, lineText } };
