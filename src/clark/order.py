"""Where a moved row goes (#74 Supporting Documents, #65 sections; the #65 design note, 28-10-2026).

New in clark; no creaite source. Pure functions with no database, generic over any table whose rows have `id` and
`sort_order`, so documents and sections share one rule. A row is a dict (or anything indexed by "id" and "sort_order").
Rows are shown by sort_order, then id.

A move writes only the moved row's sort_order, so Undo of one move never disagrees with a later move of another row:
the new value is the midpoint of its two neighbours, GAP before the first, or GAP after the last. When no whole
number fits between the neighbours (or they tie), every row is renumbered to GAP * n in the same step.
"""
GAP = 1024


def in_order(rows):
    """The rows as shown: by sort_order, then id."""
    return sorted(rows, key=lambda r: (r["sort_order"], r["id"]))


def _checked(rows):
    """The rows in order, or ValueError when an id is repeated or a sort_order isn't a whole number."""
    rows = list(rows)
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("Two rows in this list can't be told apart.")
    if any(type(r["sort_order"]) is not int for r in rows):
        raise ValueError("A row in this list has a place that isn't a whole number.")
    return in_order(rows)


def end_slot(rows):
    """The sort_order for a new row at the end: GAP after the last row, or GAP when there are none."""
    rows = _checked(rows)
    return rows[-1]["sort_order"] + GAP if rows else GAP


def section_slot(rows, moving_id, before_id):
    """The writes that move row `moving_id` to just before row `before_id` (None: to the end), as {id: new sort_order}.

    Usually one entry, the moved row's. A full renumber, every row whose value changes, GAP * 1, GAP * 2 ..., when no whole
    number fits between the two neighbours (they differ by less than 2, or tie). {} when the row is already there
    (including before itself), so nothing is written and no step is made. ValueError for an id not in `rows`."""
    rows = _checked(rows)
    ids = [r["id"] for r in rows]
    if moving_id not in ids:
        raise ValueError("That row isn't in this list.")
    if before_id is not None and before_id not in ids:
        raise ValueError("The row to move before isn't in this list.")
    if before_id == moving_id:
        return {}
    moving = rows[ids.index(moving_id)]
    others = [r for r in rows if r["id"] != moving_id]
    place = len(others) if before_id is None else [r["id"] for r in others].index(before_id)
    if place == ids.index(moving_id):
        return {}
    if place == 0:
        return {moving_id: others[0]["sort_order"] - GAP}
    if place == len(others):
        return {moving_id: others[-1]["sort_order"] + GAP}
    below, above = others[place - 1]["sort_order"], others[place]["sort_order"]
    if above - below >= 2:
        return {moving_id: (below + above) // 2}
    wanted = others[:place] + [moving] + others[place:]
    return {r["id"]: GAP * n for n, r in enumerate(wanted, 1) if r["sort_order"] != GAP * n}
