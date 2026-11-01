// The review period for the open project (#160): "Not reviewed after (days)". One number, read from the project's own setting
// (data.project.review_days) and 14 when it has none. It is handed to the filters (filters.js setReviewDays), so the chip in the
// Freshness filter, the filter's value and the Dashboard tile can never use different numbers. Nothing here is saved by itself:
// the Settings control (edit/ReviewDays.jsx) asks the server and only then changes data.project.
import { signal, computed, effect } from "@preact/signals";
import { data } from "./report.js";
import { setReviewDays } from "../filters.js";
import { daysOf } from "../reviewSetting.js";

export const reviewDays = computed(() => daysOf(data.value && data.value.project));
/** Whether the optional "Not reviewed" tile is on the Dashboard's At a glance row. Off until the eye turns it on. */
export const staleTile = signal(false);

effect(() => setReviewDays(reviewDays.value));
