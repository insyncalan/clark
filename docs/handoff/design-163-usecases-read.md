# Use Cases read route (#163)

Scope: the read route only. The published file's Use Cases tab, its absence tests and the print order moved to #168.

## What it does

`GET /api/use-cases?project=<CODE>` returns the project's use cases as the editor shows them. It reads and writes nothing.

Answer: `{"ok": true, "project": CODE, "use_cases": [...]}`, in page order (sort_order, then id). Each use case:

| Field | Meaning |
|---|---|
| id, ref, name, headline, status | the row's id, reference, title, "where it stands" line and status |
| standing | the standing text, through the rich-text allow-list |
| on_dashboard | true when the published file carries this use case, as the injected rule says (not the stored eye) |
| linked, open | all its work items, and how many are open (actions, risks and issues, decisions) |
| next_steps | its open actions: id, description, owner, due_date, status, client_visible (owner and due_date are null when missing) |
| milestones | the milestones its open next steps point at: id, name, baseline_date, forecast_date (null when missing), status, client_visible |

Archived use cases, work items and milestones are left out. Open uses `glance.is_open`, so the editor and the published counts cannot differ.

The shape for the file side (#168) is the same names. The file does not use this route: `publish.select` still decides what a client gets.

## Files

- `src/clark/use_cases_read.py` (new): the read and the cleaning. Not guarded.
- `src/clark/server.py` (GUARDED): one GET route, `use_cases_route`, one entry in `GET_ROUTES`, one seam argument `use_cases` on `LocalServer` and `serve`. No clark import added; the seam is given from `__main__`.
- `src/clark/__main__.py`: gives the seam `use_cases_read.make_read(store.data_for, use_case_ids_on_file(store))`.
- `tests/test_use_cases_read.py` (new).

No change to store.py, publish.py, the schema or any guard test.

## Reviewer attack points

1. The route takes one parameter. `project` must match the project-code shape and appear once; any other parameter, a repeat, an empty or lower-case code is 400.
2. The token and Host checks are the existing ones in `do_GET`, before the route runs.
3. Nothing is written: the seam only calls `Store.data_for` (its own read-only connection); a test compares the database file before and after.
4. The answer is built from a whitelist of fields per row. `internal_note`, `source`, `movement` and the other never-published columns are not copied. The editor's view does include the eye and items that are not client visible, by design; that is why it is not the file's source.
5. Hostile text: standing through `sanitise.clean_html` (empty if refused for length); plain fields lose control, surrogate and invisible formatting characters (as the file's reason text does) and are **not cut**, so the editor shows the file's own words; a value that is not text is empty; a missing owner or date is null. Standing text over the cleaner's length comes back empty, so **the page must not save a use case from this payload**. The page must still escape what it draws.
6. A server given no reader answers 404 not_found before anything else is checked, so the route does not exist by accident, whatever the request.
7. `on_dashboard` is not decided here. `make_read(data_for, client_ids)` takes `client_ids(code)`, a function that returns the set of use case ids the published file carries. Until #168 adds `publish.client_use_cases`, `__main__.use_case_ids_on_file` supplies it from `publish.select` over `publish.read_inputs` (so Sensitive labels, rows left off the page and hidden sections count); it is the one place to point at a teammate's function. Tests use a stand-in. Signature needed from #168: `client_use_cases(inputs) -> list of the kept use case rows` (inputs as `publish.read_inputs` gives), or any function giving the ids for a project code.
8. Milestones: a milestone belongs to a use case when one of its **open** next steps names it (`use_cases_read.milestones_of`, the one place in the route). This is the published file's rule (#168's decision 2), so the editor and the file cannot disagree about which milestone belongs where. The route cannot call `publish.client_use_cases` yet (it is not on main, and it returns ids of the client's rows, not the editor's full rows with the eye and the items that are not client visible). When it lands, `use_case_ids_on_file` is pointed at it for `on_dashboard`, and `milestones_of` is either replaced by its milestone ids or kept as the editor's rule with a test that the two agree. The signature #168 chose, `client_use_cases(data, code, hidden_ids, label_rules, hidden_types)`, differs from the `inputs` form asked for here; the launcher adapts it.
9. Two reads: `data_for` and `read_inputs` each open their own read-only connection, so a write between them can show one inconsistent answer (a new use case reads as off until the next GET). Fine for an editor view.

## Data shape

```json
{"ok": true, "project": "PUB", "use_cases": [
  {"id": "PUB-U-001", "ref": "1.1", "name": "Passenger flow", "headline": "Going to plan", "status": "On track",
   "standing": "<p>Gates are in.</p>", "on_dashboard": true, "linked": 3, "open": 2,
   "next_steps": [{"id": "PUB-A-001", "description": "Agree the plan", "owner": "Sam Carter", "due_date": "2026-11-05",
                   "status": "Open", "client_visible": true}],
   "milestones": [{"id": "PUB-M-001", "name": "Gates live", "baseline_date": "2026-11-20", "forecast_date": null,
                   "status": "Planned", "client_visible": true}]}]}
```
