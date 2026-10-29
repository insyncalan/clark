"""A small workbook maker for the Excel import tests (#38), in the shape the import expects (see src/clark/excel_import.py):
sheets Actions, RAID, Decisions, Milestones, Use cases; row 1 the table's column names as store.columns() gives them; dates
as real Excel dates; flags as Yes or No. It stands in for the export (#37) until that is merged."""
from datetime import date

import _paths  # noqa: F401
from clark.store import DATE_FIELDS, columns
from openpyxl import Workbook, load_workbook

SHEETS = (("Actions", "actions"), ("RAID", "raid"), ("Decisions", "decisions"), ("Milestones", "milestones"),
          ("Use cases", "use_cases"))
FLAGS = {"client_visible", "state_set", "active"}


def cell_of(field, value):
    """A stored value as the export puts it in a cell."""
    if value is None:
        return None
    if field in DATE_FIELDS:
        return date.fromisoformat(value)
    if field in FLAGS:
        return "Yes" if int(value) else "No"
    return value


def make_workbook(store, path, project="ABC", sheets=None):
    """Write every row of `project` to `path`; `sheets` limits which sheets (by table name). Returns the path."""
    wb = Workbook()
    wb.remove(wb.active)
    for name, table in SHEETS:
        if sheets is not None and table not in sheets:
            continue
        ws = wb.create_sheet(name)
        cols = columns(store.con, table)
        ws.append(cols)
        for r in sorted(store.read(table, project=project), key=lambda r: r["id"]):
            ws.append([cell_of(c, r[c]) for c in cols])
    wb.save(str(path))
    return path


def _sheet(wb, name):
    return wb[name]


def _col(ws, field):
    for c in ws[1]:
        if c.value == field:
            return c.column
    raise KeyError(field)


def _row_of(ws, item_id):
    col = _col(ws, "id")
    for r in range(2, ws.max_row + 1):
        if ws.cell(r, col).value == item_id:
            return r
    raise KeyError(item_id)


def edit(path, sheet, item_id, **cells):
    """Set cells of the row with this id (None clears a cell)."""
    wb = load_workbook(str(path))
    ws = _sheet(wb, sheet)
    r = _row_of(ws, item_id)
    for f, v in cells.items():
        ws.cell(r, _col(ws, f)).value = v
    wb.save(str(path))


def add_row(path, sheet, **cells):
    """Append a row (leave `id` out for a new item)."""
    wb = load_workbook(str(path))
    ws = _sheet(wb, sheet)
    ws.append([cells.get(c.value) for c in ws[1]])
    wb.save(str(path))


def drop_row(path, sheet, item_id):
    wb = load_workbook(str(path))
    ws = _sheet(wb, sheet)
    ws.delete_rows(_row_of(ws, item_id))
    wb.save(str(path))


def rename_header(path, sheet, old, new):
    wb = load_workbook(str(path))
    ws = _sheet(wb, sheet)
    ws.cell(1, _col(ws, old)).value = new
    wb.save(str(path))
